import pandas as pd
import os
import sys
from .embedding_model import EmbeddingBasedModel
from .split_data import split_train_test

def train_model():
    """Train the embedding model and generate predictions."""
    base_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    processed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
    os.makedirs(processed_path, exist_ok=True)
    
    print("=" * 80)
    print("EMBEDDING MODEL TRAINING")
    print("=" * 80)
    
    # Step 1: Split data
    print("\n[Step 1] Splitting data into train and test...")
    train_data, test_data = split_train_test(test_size=0.3, random_state=42)
    soan user data for similarity target...")
    loan_users = test_data[test_data['has_home_loan'] == 1].copy()
    
    if len(loan_users) == 0 or len(loan_users) < 10:
        print("Warning: No loan users in test set. Using all available loan data...")
        # Load all loan data
        loan_df = pd.read_csv(os.path.join(base_path, 'loan.asc'), sep=';')
        account_df = pd.read_csv(os.path.join(base_path, 'account.asc'), sep=';')
        client_df = pd.read_csv(os.path.join(base_path, 'client.asc'), sep=';')
        disp_df = pd.read_csv(os.path.join(base_path, 'disp.asc'), sep=';')
        district_df = pd.read_csv(os.path.join(base_path, 'district.asc'), sep=';')
        district_df.rename(columns={'A1': 'district_id'}, inplace=True)
        trans_df = pd.read_csv(os.path.join(base_path, 'trans.asc'), sep=';', low_memory=False)
        
        # Merge to get full user data
        data = disp_df.merge(client_df, on='client_id', how='left')
        data = data.merge(account_df, on='account_id', how='left', suffixes=('_client', '_account'))
        if 'district_id_client' in data.columns and 'district_id_account' in data.columns:
            data['district_id'] = data['district_id_client'].fillna(data['district_id_account'])
            data.drop(columns=['district_id_client', 'district_id_account'], inplace=True)
        elif 'district_id_client' in data.columns:
            data['district_id'] = data['district_id_client']
            data.drop(columns=['district_id_client'], inplace=True)
        elif 'district_id_account' in data.columns:
            data['district_id'] = data['district_id_account']
            data.drop(columns=['district_id_account'], inplace=True)
        
        data = data.merge(district_df, on='district_id', how='left')
        data = data.merge(loan_df, on='account_id', how='left')
        
        # Aggregate transactions
        trans_agg = trans_df.groupby('account_id').agg({
            'amount': ['mean', 'sum', 'count'],
            'balance': ['mean', 'max', 'min', 'last']
        }).reset_index()
        trans_agg.columns = ['account_id', 'amount_mean', 'amount_sum', 'amount_count', 
                            'balance_mean', 'balance_max', 'balance_min', 'balance_last']
        data = data.merge(trans_agg, on='account_id', how='left')
        
        # Ensure district_avg_salary is available
        if 'A11' in data.columns:
            data['district_avg_salary'] = pd.to_numeric(data['A11'], errors='coerce').fillna(0)
        
        # Get users with loans
        loan_users = data[data['loan_id'].notnull()].copy()
        # One row per client
        loan_users = loan_users.sort_values('balance_last', ascending=False).drop_duplicates('client_id', keep='first')
    
    print(f"Loan users for similarity target: {len(loan_users)}")
    
    # Step 3: Train the embedding model
    print("\n[Step 3] Training embedding model...")
    model = EmbeddingBasedModel(embedding_dim=64, device='cpu')
    model.fit(
        train_data=train_data,
        loan_user_data=loan_users,
        epochs=100,
        batch_size=32,
        lr=0.001
    )
    
    # Step 4: Generate predictions on training data
    print("\n[Step 4] Generating similarity scores for training data...")
    train_predictions = model.predict_similarity(train_data)
    
    # Step 5: Save top users to train_output.csv
    print("\n[Step 5] Saving top users to train_output.csv...")
    # Select top N users (e.g., top 20% or top 100)
    top_n = max(100, int(len(train_predictions) * 0.2))
    top_users = train_predictions.head(top_n).copy()
    
    output_path = os.path.join(processed_path, 'train_output.csv')
    top_users.to_csv(output_path, index=False)
    
    print(f"Top {top_n} users saved to: {output_path}")
    print(f"Similarity score range: {top_users['similarity_score'].min():.4f} - {top_users['similarity_score'].max():.4f}")
    
    # Step 6: Save the trained model
    print("\n[Step 6] Saving trained model...")
    model_path = os.path.join(processed_path, 'embedding_model.pth')
    model.save(model_path)
    
    print("\n" + "=" * 80)
    print("✅ TRAINING COMPLETE!")
    print("=" * 80)
    print(f"Model saved to: {model_path}")
    print(f"Top users saved to: {output_path}")
    
    return model, train_predictions

if __name__ == '__main__':
    model, predictions = train_model()

