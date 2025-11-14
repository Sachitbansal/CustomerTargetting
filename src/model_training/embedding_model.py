"""
Embedding-based model for user similarity matching.
Generates embeddings for users and uses cosine similarity to find similar users.
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import os
import pickle

class UserEmbeddingModel(nn.Module):
    """
    Neural network model to generate user embeddings.
    Focuses on important features for home loan targeting.
    """
    
    def __init__(self, input_dim, embedding_dim=64, hidden_dims=[128, 64]):
        super(UserEmbeddingModel, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        # Build hidden layers
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev_dim = hidden_dim
        
        # Final embedding layer
        layers.append(nn.Linear(prev_dim, embedding_dim))
        
        self.network = nn.Sequential(*layers)
        
    def forward(self, x):
        """Generate embeddings for input features."""
        return self.network(x)
    
    def get_embedding(self, x):
        """Get normalized embeddings."""
        embedding = self.forward(x)
        # Normalize embeddings for cosine similarity
        return torch.nn.functional.normalize(embedding, p=2, dim=1)


class EmbeddingBasedModel:
    """
    Complete embedding-based model for user targeting.
    Uses cosine similarity to find users similar to those with home loans.
    """
    
    def __init__(self, embedding_dim=64, device='cpu'):
        self.embedding_dim = embedding_dim
        self.device = device
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.loan_user_embeddings = None
        
    def _prepare_features(self, data_df):
        """
        Extract and prepare features for embedding generation.
        Focuses on important features for home loan targeting.
        """
        # Select important features for home loan targeting
        important_features = [
            'age', 'balance_last', 'balance_mean', 'balance_max', 'balance_min',
            'amount_mean', 'amount_sum', 'amount_count',
            'district_avg_salary',  # Will be added if available
            'txn_count',  # Will be computed
        ]
        
        # Compute age if birth_number exists
        if 'birth_number' in data_df.columns:
            from ..utils.features import _parse_birth_number
            data_df = data_df.copy()
            data_df['age'] = data_df['birth_number'].apply(_parse_birth_number)
            data_df['age'] = data_df['age'].fillna(data_df['age'].median())
        
        # Compute transaction count if not present
        if 'amount_count' in data_df.columns:
            data_df['txn_count'] = data_df['amount_count']
        else:
            data_df['txn_count'] = 0
        
        # Get district average salary if available
        if 'A11' in data_df.columns:
            data_df['district_avg_salary'] = pd.to_numeric(data_df['A11'], errors='coerce').fillna(0)
        elif 'district_avg_salary' not in data_df.columns:
            data_df['district_avg_salary'] = 0
        
        # Fill missing values
        for feat in important_features:
            if feat not in data_df.columns:
                data_df[feat] = 0
            data_df[feat] = pd.to_numeric(data_df[feat], errors='coerce').fillna(0)
        
        # Select and order features
        available_features = [f for f in important_features if f in data_df.columns]
        feature_data = data_df[available_features].copy()
        
        return feature_data, available_features
    
    def fit(self, train_data, loan_user_data, epochs=50, batch_size=32, lr=0.001):
        """
        Train the embedding model.
        
        Args:
            train_data: DataFrame with users without loans (for training)
            loan_user_data: DataFrame with users who have home loans (for similarity target)
            epochs: Number of training epochs
            batch_size: Batch size for training
            lr: Learning rate
        """
        print("Preparing features...")
        train_features, feature_cols = self._prepare_features(train_data)
        loan_features, _ = self._prepare_features(loan_user_data)
        
        self.feature_columns = feature_cols
        
        # Scale features
        all_features = pd.concat([train_features, loan_features], axis=0)
        self.scaler.fit(all_features)
        
        train_scaled = self.scaler.transform(train_features)
        loan_scaled = self.scaler.transform(loan_features)
        
        # Convert to tensors
        train_tensor = torch.FloatTensor(train_scaled).to(self.device)
        loan_tensor = torch.FloatTensor(loan_scaled).to(self.device)
        
        # Initialize model
        input_dim = len(feature_cols)
        self.model = UserEmbeddingModel(input_dim, self.embedding_dim).to(self.device)
        optimizer = optim.Adam(self.model.parameters(), lr=lr)
        
        print(f"Training embedding model...")
        print(f"Input dimension: {input_dim}, Embedding dimension: {self.embedding_dim}")
        print(f"Training samples: {len(train_tensor)}, Loan user samples: {len(loan_tensor)}")
        
        # Training loop: maximize similarity between train users and loan users
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            
            # Get embeddings
            train_embeddings = self.model.get_embedding(train_tensor)
            loan_embeddings = self.model.get_embedding(loan_tensor)
            
            # Compute average loan user embedding (centroid)
            loan_centroid = loan_embeddings.mean(dim=0, keepdim=True)
            
            # Compute cosine similarity between train users and loan centroid
            similarities = torch.mm(train_embeddings, loan_centroid.t()).squeeze()
            
            # Loss: maximize similarity (minimize negative similarity)
            loss = -similarities.mean()
            
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                avg_sim = -loss.item()
                print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}, Avg Similarity: {avg_sim:.4f}")
        
        # Store loan user embeddings for inference
        self.model.eval()
        with torch.no_grad():
            self.loan_user_embeddings = self.model.get_embedding(loan_tensor).cpu().numpy()
        
        print("✅ Model training complete!")
    
    def predict_similarity(self, user_data):
        """
        Predict similarity scores for users.
        Returns sorted DataFrame with similarity scores.
        """
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        
        self.model.eval()
        
        # Prepare features
        user_features, _ = self._prepare_features(user_data)
        
        # Ensure same feature order
        for col in self.feature_columns:
            if col not in user_features.columns:
                user_features[col] = 0
        
        user_features = user_features[self.feature_columns]
        
        # Scale and convert to tensor
        user_scaled = self.scaler.transform(user_features)
        user_tensor = torch.FloatTensor(user_scaled).to(self.device)
        
        # Get embeddings
        with torch.no_grad():
            user_embeddings = self.model.get_embedding(user_tensor).cpu().numpy()
        
        # Compute cosine similarity with loan users
        similarities = cosine_similarity(user_embeddings, self.loan_user_embeddings)
        
        # Average similarity across all loan users
        avg_similarities = similarities.mean(axis=1)
        
        # Create results DataFrame
        results = user_data.copy()
        results['similarity_score'] = avg_similarities
        
        # Sort by similarity (highest first)
        results = results.sort_values('similarity_score', ascending=False).reset_index(drop=True)
        
        return results
    
    def save(self, filepath):
        """Save model and scaler."""
        save_dir = os.path.dirname(filepath)
        os.makedirs(save_dir, exist_ok=True)
        
        # Save model state
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'embedding_dim': self.embedding_dim,
            'feature_columns': self.feature_columns,
            'loan_user_embeddings': self.loan_user_embeddings,
        }, filepath)
        
        # Save scaler separately
        scaler_path = filepath.replace('.pth', '_scaler.pkl')
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        print(f"Model saved to: {filepath}")
        print(f"Scaler saved to: {scaler_path}")
    
    def load(self, filepath):
        """Load model and scaler."""
        # Load model state
        checkpoint = torch.load(filepath, map_location=self.device)
        
        input_dim = len(checkpoint['feature_columns'])
        self.model = UserEmbeddingModel(input_dim, checkpoint['embedding_dim']).to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        self.embedding_dim = checkpoint['embedding_dim']
        self.feature_columns = checkpoint['feature_columns']
        self.loan_user_embeddings = checkpoint['loan_user_embeddings']
        
        # Load scaler
        scaler_path = filepath.replace('.pth', '_scaler.pkl')
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
        
        print(f"Model loaded from: {filepath}")

