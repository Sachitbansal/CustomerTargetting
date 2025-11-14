import pickle
import numpy as np
import os
import pandas as pd

class DummyModel:
    """Simple rule-based model for demonstration."""
    
    def predict(self, feats):
        """
        Predict likelihood of accepting offer.
        
        Args:
            feats: Dictionary of features
            
        Returns:
            float: Probability score between 0 and 1
        """
        score = 0.0
        
        # Rule 1: Balance threshold
        balance = feats.get('balance', 0)
        if balance > 100000:
            score += 0.3
        elif balance > 50000:
            score += 0.2
        elif balance > 20000:
            score += 0.1
        
        # Rule 2: Income threshold
        income = feats.get('income', feats.get('estimated_income', 0))
        if income > 50000:
            score += 0.3
        elif income > 35000:
            score += 0.2
        elif income > 25000:
            score += 0.1
        
        # Rule 3: Activity score
        activity = feats.get('activity_score', 0)
        score += activity * 0.2
        
        # Rule 4: Age factor (prefer middle-aged)
        age = feats.get('age', feats.get('estimated_age', 0))
        if 30 <= age <= 50:
            score += 0.2
        elif 25 <= age < 30 or 50 < age <= 60:
            score += 0.1
        
        # Cap at 1.0
        score = min(score, 1.0)
        
        return round(score, 3)
    
    def predict_binary(self, feats):
        """Return binary prediction (True/False) based on threshold."""
        prob = self.predict(feats)
        return prob >= 0.5


class EmbeddingModelWrapper:
    """Wrapper to use embedding model with the same interface as DummyModel."""
    
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
    
    def predict(self, feats):
        """
        Predict similarity score for a single user.
        
        Args:
            feats: Dictionary of features
            
        Returns:
            float: Similarity score between 0 and 1 (normalized)
        """
        # Convert features dict to DataFrame
        feats_df = pd.DataFrame([feats])
        
        # Get similarity score
        try:
            results = self.embedding_model.predict_similarity(feats_df)
            similarity = results.iloc[0]['similarity_score']
            
            # Normalize to 0-1 range (cosine similarity is -1 to 1, but embeddings are normalized so 0-1)
            # Add 1 and divide by 2 to map to 0-1
            normalized_score = (similarity + 1) / 2
            return round(normalized_score, 3)
        except Exception as e:
            # Fallback to 0 if prediction fails
            print(f"Warning: Embedding prediction failed: {e}")
            return 0.0
    
    def predict_binary(self, feats):
        """Return binary prediction (True/False) based on threshold."""
        prob = self.predict(feats)
        return prob >= 0.5


def load_model(product_type='home_loan'):
    """
    Load model for the specified product type.
    
    Args:
        product_type: Type of product (e.g., 'home_loan', 'life_insurance')
        
    Returns:
        Model object with predict() method
    """
    # Try to load embedding model first
    processed_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed')
    model_path = os.path.join(processed_path, 'embedding_model.pth')
    
    if os.path.exists(model_path):
        try:
            from .embedding_model import EmbeddingBasedModel
            embedding_model = EmbeddingBasedModel(embedding_dim=64, device='cpu')
            embedding_model.load(model_path)
            print("Loaded embedding-based model")
            return EmbeddingModelWrapper(embedding_model)
        except Exception as e:
            print(f"Warning: Could not load embedding model: {e}")
            print("Falling back to rule-based model")
    
    # Fallback to rule-based model
    return DummyModel()
