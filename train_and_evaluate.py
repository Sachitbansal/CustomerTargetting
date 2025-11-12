"""
Main script to train and evaluate the embedding-based model.
Run this script to:
1. Split data into train/test
2. Train the embedding model
3. Evaluate on test data
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.train_embedding_model import train_model
from src.evaluate_model import evaluate_model

if __name__ == '__main__':
    print("Starting training and evaluation pipeline...")
    print("=" * 80)
    
    # Step 1: Train the model
    print("\n[PHASE 1] TRAINING")
    model, train_predictions = train_model()
    
    # Step 2: Evaluate the model
    print("\n\n[PHASE 2] EVALUATION")
    test_predictions = evaluate_model()
    
    print("\n" + "=" * 80)
    print("✅ PIPELINE COMPLETE!")
    print("=" * 80)

