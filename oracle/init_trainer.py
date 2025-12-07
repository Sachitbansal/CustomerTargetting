"""
Oracle Neural Network Training Script
Trains a fully-connected NN to predict target variables for the TargettedCalling system
Saves trained models to ./models directory
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import os
from pathlib import Path
from datetime import datetime
import json

# Configuration
TARGET_VARIABLE = "opted_car_loan"  # Change this to train different models
# Options: "opted_home_loan", "opted_car_loan", "recommend_elss", "recommend_nifty50"

DATA_PATH = Path(__file__).parent.parent / "customers_master_multi_product.csv"
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Training hyperparameters
BATCH_SIZE = 32
LEARNING_RATE = 0.001
EPOCHS = 50
EARLY_STOPPING_PATIENCE = 10
VALIDATION_SPLIT = 0.2
TEST_SPLIT = 0.15
RANDOM_STATE = 42

# Feature configuration
NUMERICAL_FEATURES = [
    'age', 'dependents_count', 'yearly_income', 'account_age_months',
    'initial_credit_score', 'existing_loans_count', 'existing_loan_monthly_EMI_total',
    'total_credit_limit', 'initial_credit_utilization_ratio', 'initial_avg_monthly_balance',
    'initial_savings_rate', 'txn_count_last_30d', 'high_value_txn_count_30d',
    'bounced_txn_count', 'final_avg_monthly_balance', 'monthly_fuel_spend',
    'monthly_transport_service_spend', 'avg_monthly_investment_debit', 'final_credit_score',
    'dti_ratio', 'savings_rate', 'income_to_limit', 'txn_intensity',
    'age_x_dependents', 'score_x_log_income'
]

CATEGORICAL_FEATURES = [
    'gender', 'marital_status', 'employment_type', 'occupation',
    'education_level', 'city_tier', 'has_existing_auto_loan',
    'has_existing_investment_account'
]

# Device configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")


class CustomerDataset(Dataset):
    """PyTorch Dataset for customer data"""
    
    def __init__(self, features, labels):
        self.features = torch.FloatTensor(features)
        self.labels = torch.FloatTensor(labels)
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]


class OracleNN(nn.Module):
    """Fully-connected Neural Network Oracle"""
    
    def __init__(self, input_dim, hidden_dims=[128, 64, 32]):
        super(OracleNN, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_dim = hidden_dim
        
        # Output layer
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)


def load_and_preprocess_data(target_column):
    """Load data and perform preprocessing"""
    print(f"\n{'='*70}")
    print(f"Loading data from: {DATA_PATH}")
    print(f"Target variable: {target_column}")
    print(f"{'='*70}\n")
    
    # Load data
    df = pd.read_csv(DATA_PATH)
    print(f"✅ Loaded {len(df)} records")
    
    # Check if target exists
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in data")
    
    # Separate features and target
    X = df[NUMERICAL_FEATURES + CATEGORICAL_FEATURES].copy()
    y = df[target_column].values
    
    print(f"📊 Class distribution:")
    print(f"   Positive (1): {np.sum(y == 1)} ({np.mean(y)*100:.2f}%)")
    print(f"   Negative (0): {np.sum(y == 0)} ({(1-np.mean(y))*100:.2f}%)")
    
    # Handle categorical features
    label_encoders = {}
    X_encoded = X.copy()
    
    for col in CATEGORICAL_FEATURES:
        le = LabelEncoder()
        X_encoded[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le
    
    # Handle missing values
    X_encoded = X_encoded.fillna(X_encoded.mean())
    
    # Scale numerical features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_encoded)
    
    print(f"✅ Preprocessing complete")
    print(f"   Feature dimension: {X_scaled.shape[1]}")
    
    return X_scaled, y, scaler, label_encoders


def train_model(model, train_loader, val_loader, criterion, optimizer, epochs, patience):
    """Train the neural network with early stopping"""
    
    best_val_loss = float('inf')
    patience_counter = 0
    train_losses = []
    val_losses = []
    
    print(f"\n{'='*70}")
    print("Starting training...")
    print(f"{'='*70}\n")
    
    for epoch in range(epochs):
        # Training phase
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for features, labels in train_loader:
            features, labels = features.to(device), labels.to(device)
            
            # Forward pass
            outputs = model(features).squeeze()
            loss = criterion(outputs, labels)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            predictions = (outputs > 0.5).float()
            train_correct += (predictions == labels).sum().item()
            train_total += labels.size(0)
        
        train_loss /= len(train_loader)
        train_acc = train_correct / train_total
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for features, labels in val_loader:
                features, labels = features.to(device), labels.to(device)
                outputs = model(features).squeeze()
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                predictions = (outputs > 0.5).float()
                val_correct += (predictions == labels).sum().item()
                val_total += labels.size(0)
        
        val_loss /= len(val_loader)
        val_acc = val_correct / val_total
        
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        
        # Print progress
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1:3d}/{epochs}] | "
                  f"Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.4f} | "
                  f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model
            best_model_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\n⏹️  Early stopping triggered at epoch {epoch+1}")
                print(f"   Best validation loss: {best_val_loss:.4f}")
                model.load_state_dict(best_model_state)
                break
    
    return model, train_losses, val_losses


def evaluate_model(model, test_loader):
    """Evaluate model on test set"""
    
    model.eval()
    all_preds = []
    all_labels = []
    all_probs = []
    
    with torch.no_grad():
        for features, labels in test_loader:
            features = features.to(device)
            outputs = model(features).squeeze()
            probs = outputs.cpu().numpy()
            predictions = (outputs > 0.5).float().cpu().numpy()
            
            all_probs.extend(probs)
            all_preds.extend(predictions)
            all_labels.extend(labels.numpy())
    
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    all_probs = np.array(all_probs)
    
    print(f"\n{'='*70}")
    print("Test Set Evaluation")
    print(f"{'='*70}\n")
    
    # Confusion Matrix
    cm = confusion_matrix(all_labels, all_preds)
    print("Confusion Matrix:")
    print(cm)
    print()
    
    # Classification Report
    print("Classification Report:")
    print(classification_report(all_labels, all_preds, zero_division=0))
    
    # ROC AUC Score
    try:
        auc = roc_auc_score(all_labels, all_probs)
        print(f"ROC AUC Score: {auc:.4f}")
    except:
        print("ROC AUC Score: N/A (only one class present)")
    
    return all_preds, all_labels, all_probs


def save_model_and_metadata(model, scaler, label_encoders, target_column, metadata):
    """Save trained model and preprocessing artifacts"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = f"oracle_{target_column}_{timestamp}"
    
    # Save paths
    model_path = MODEL_DIR / f"{model_name}.pth"
    scaler_path = MODEL_DIR / f"scaler_{target_column}.pkl"
    encoders_path = MODEL_DIR / f"encoders_{target_column}.pkl"
    metadata_path = MODEL_DIR / f"metadata_{target_column}.json"
    
    # Save PyTorch model
    torch.save({
        'model_state_dict': model.state_dict(),
        'input_dim': model.network[0].in_features,
        'hidden_dims': [128, 64, 32],
        'target_column': target_column,
        'timestamp': timestamp
    }, model_path)
    
    # Save scaler
    import pickle
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save label encoders
    with open(encoders_path, 'wb') as f:
        pickle.dump(label_encoders, f)
    
    # Save metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)
    
    print(f"\n{'='*70}")
    print("✅ Model and artifacts saved successfully!")
    print(f"{'='*70}")
    print(f"📁 Model: {model_path}")
    print(f"📁 Scaler: {scaler_path}")
    print(f"📁 Encoders: {encoders_path}")
    print(f"📁 Metadata: {metadata_path}")
    print(f"{'='*70}\n")


def main():
    """Main training pipeline"""
    
    print(f"\n{'='*70}")
    print(f"🚀 Oracle Neural Network Training Pipeline")
    print(f"{'='*70}")
    print(f"Target: {TARGET_VARIABLE}")
    print(f"Device: {device}")
    print(f"{'='*70}\n")
    
    # Load and preprocess data
    X, y, scaler, label_encoders = load_and_preprocess_data(TARGET_VARIABLE)
    
    # Split data: train/val/test
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=TEST_SPLIT, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=VALIDATION_SPLIT/(1-TEST_SPLIT), 
        random_state=RANDOM_STATE, stratify=y_temp
    )
    
    print(f"\n📊 Data splits:")
    print(f"   Train: {len(X_train)} samples")
    print(f"   Val:   {len(X_val)} samples")
    print(f"   Test:  {len(X_test)} samples")
    
    # Create datasets and dataloaders
    train_dataset = CustomerDataset(X_train, y_train)
    val_dataset = CustomerDataset(X_val, y_val)
    test_dataset = CustomerDataset(X_test, y_test)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # Initialize model
    input_dim = X.shape[1]
    model = OracleNN(input_dim=input_dim).to(device)
    
    print(f"\n🧠 Model architecture:")
    print(model)
    print(f"\nTotal parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Loss and optimizer
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    # Train model
    model, train_losses, val_losses = train_model(
        model, train_loader, val_loader, criterion, optimizer, 
        EPOCHS, EARLY_STOPPING_PATIENCE
    )
    
    # Evaluate on test set
    predictions, labels, probabilities = evaluate_model(model, test_loader)
    
    # Save model and metadata
    metadata = {
        'target_column': TARGET_VARIABLE,
        'training_date': datetime.now().isoformat(),
        'n_features': input_dim,
        'n_train_samples': len(X_train),
        'n_val_samples': len(X_val),
        'n_test_samples': len(X_test),
        'hyperparameters': {
            'batch_size': BATCH_SIZE,
            'learning_rate': LEARNING_RATE,
            'epochs': EPOCHS,
            'early_stopping_patience': EARLY_STOPPING_PATIENCE
        },
        'feature_columns': {
            'numerical': NUMERICAL_FEATURES,
            'categorical': CATEGORICAL_FEATURES
        }
    }
    
    save_model_and_metadata(model, scaler, label_encoders, TARGET_VARIABLE, metadata)
    
    print("🎉 Training pipeline completed successfully!")


if __name__ == "__main__":
    main()