"""
Evaluation script for embedding-based model.
Tests the model on test dataset and checks if top users are those with loans.
"""
import pandas as pd
import os
from .embedding_model import EmbeddingBasedModel

def evaluate_model():
    """Evaluate the trained model on test data."""
    processed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
    
    print("=" * 80)
    print("MODEL EVALUATION")
    print("=" * 80)
    
    # Step 1: Load test data
    print("\n[Step 1] Loading test data...")
    test_path = os.path.join(processed_path, 'test_data.csv')
    if not os.path.exists(test_path):
        print("Error: test_data.csv not found. Please run split_data.py first.")
        return
    
    test_data = pd.read_csv(test_path)
    print(f"Test data loaded: {len(test_data)} users")
    print(f"  - With loans: {test_data['has_home_loan'].sum()}")
    print(f"  - Without loans: {(~test_data['has_home_loan'].astype(bool)).sum()}")
    
    # Step 2: Load trained model
    print("\n[Step 2] Loading trained model...")
    model_path = os.path.join(processed_path, 'embedding_model.pth')
    if not os.path.exists(model_path):
        print("Error: embedding_model.pth not found. Please run train_embedding_model.py first.")
        return
    
    model = EmbeddingBasedModel(embedding_dim=64, device='cpu')
    model.load(model_path)
    
    # Step 3: Generate predictions
    print("\n[Step 3] Generating similarity scores for test data...")
    test_predictions = model.predict_similarity(test_data)
    
    # Step 4: Evaluate results
    print("\n[Step 4] Evaluating results...")
    
    # Check top users (should be those with loans)
    top_n = min(100, len(test_predictions))
    top_users = test_predictions.head(top_n)
    top_loan_count = top_users['has_home_loan'].sum()
    top_loan_percentage = (top_loan_count / top_n) * 100
    
    # Check bottom users (should be those without loans)
    bottom_n = min(100, len(test_predictions))
    bottom_users = test_predictions.tail(bottom_n)
    bottom_loan_count = bottom_users['has_home_loan'].sum()
    bottom_loan_percentage = (bottom_loan_count / bottom_n) * 100
    
    print(f"\nTop {top_n} users (highest similarity):")
    print(f"  - Users with loans: {top_loan_count} ({top_loan_percentage:.1f}%)")
    print(f"  - Users without loans: {top_n - top_loan_count} ({100 - top_loan_percentage:.1f}%)")
    
    print(f"\nBottom {bottom_n} users (lowest similarity):")
    print(f"  - Users with loans: {bottom_loan_count} ({bottom_loan_percentage:.1f}%)")
    print(f"  - Users without loans: {bottom_n - bottom_loan_count} ({100 - bottom_loan_percentage:.1f}%)")
    
    # Overall statistics
    print(f"\nOverall Statistics:")
    print(f"  - Total test users: {len(test_predictions)}")
    print(f"  - Users with loans: {test_predictions['has_home_loan'].sum()}")
    print(f"  - Users without loans: {(~test_predictions['has_home_loan'].astype(bool)).sum()}")
    print(f"  - Average similarity (with loans): {test_predictions[test_predictions['has_home_loan']==1]['similarity_score'].mean():.4f}")
    print(f"  - Average similarity (without loans): {test_predictions[test_predictions['has_home_loan']==0]['similarity_score'].mean():.4f}")
    
    # Calculate metrics
    # Precision@K: Of top K users, how many have loans?
    k_values = [10, 20, 50, 100]
    print(f"\nPrecision@K (higher is better):")
    for k in k_values:
        if k <= len(test_predictions):
            top_k = test_predictions.head(k)
            precision_k = top_k['has_home_loan'].sum() / k
            print(f"  - Precision@{k}: {precision_k:.3f} ({top_k['has_home_loan'].sum()}/{k})")
    
    # Step 5: Save results
    print("\n[Step 5] Saving evaluation results...")
    output_path = os.path.join(processed_path, 'test_predictions.csv')
    test_predictions.to_csv(output_path, index=False)
    print(f"Test predictions saved to: {output_path}")
    
    # Step 6: Summary
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    if top_loan_percentage > 50:
        print("✅ GOOD: Top users are mostly those with loans!")
    else:
        print("⚠️  WARNING: Top users should have more loan takers.")
    
    if bottom_loan_percentage < 50:
        print("✅ GOOD: Bottom users are mostly those without loans!")
    else:
        print("⚠️  WARNING: Bottom users should have fewer loan takers.")
    
    print("\n" + "=" * 80)
    
    return test_predictions

if __name__ == '__main__':
    results = evaluate_model()

