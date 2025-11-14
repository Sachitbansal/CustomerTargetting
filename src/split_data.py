import pandas as pd
import numpy as np
import os

def split_train_test(test_size=0.3, random_state=42):
    """
    Split data into train and test sets.
    For training: Remove some users with loans (keep only users without loans)
    For test: Keep both users with and without loans
    
    Args:
        test_size: Proportion of data to use for testing
        random_state: Random seed for reproducibility
    """
    base_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    processed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
    os.makedirs(processed_path, exist_ok=True)
    
    print("Loading data files...")
    # Load all necessary files
    account = pd.read_csv(os.path.join(base_path, 'account.asc'), sep=';')
    client = pd.read_csv(os.path.join(base_path, 'client.asc'), sep=';')
    disp = pd.read_csv(os.path.join(base_path, 'disp.asc'), sep=';')
    district = pd.read_csv(os.path.join(base_path, 'district.asc'), sep=';')
    district.rename(columns={'A1': 'district_id'}, inplace=True)
    loan = pd.read_csv(os.path.join(base_path, 'loan.asc'), sep=';')
    trans = pd.read_csv(os.path.join(base_path, 'trans.asc'), sep=';', low_memory=False)
    
    print("Merging data...")
    # Merge to create user-level dataset
    data = disp.merge(client, on='client_id', how='left')
    data = data.merge(account, on='account_id', how='left', suffixes=('_client', '_account'))
    
    # Handle district_id
    if 'district_id_client' in data.columns and 'district_id_account' in data.columns:
        data['district_id'] = data['district_id_client'].fillna(data['district_id_account'])
        data.drop(columns=['district_id_client', 'district_id_account'], inplace=True)
    elif 'district_id_client' in data.columns:
        data['district_id'] = data['district_id_client']
        data.drop(columns=['district_id_client'], inplace=True)
    elif 'district_id_account' in data.columns:
        data['district_id'] = data['district_id_account']
        data.drop(columns=['district_id_account'], inplace=True)
    
    data = data.merge(district, on='district_id', how='left', suffixes=('', '_district'))
    
    # Merge loan data to identify users with loans
    data = data.merge(loan, on='account_id', how='left', suffixes=('', '_loan'))
    
    # Aggregate transaction data per account
    print("Aggregating transaction data...")
    trans_agg = trans.groupby('account_id').agg({
        'amount': ['mean', 'sum', 'count'],
        'balance': ['mean', 'max', 'min', 'last']
    }).reset_index()
    trans_agg.columns = ['account_id', 'amount_mean', 'amount_sum', 'amount_count', 
                        'balance_mean', 'balance_max', 'balance_min', 'balance_last']
    data = data.merge(trans_agg, on='account_id', how='left')
    
    # Ensure district_avg_salary is available (from A11 column)
    if 'A11' in data.columns:
        data['district_avg_salary'] = pd.to_numeric(data['A11'], errors='coerce').fillna(0)
    
    # Create target variable: has_home_loan (assuming all loans are home loans for now)
    data['has_home_loan'] = data['loan_id'].notnull().astype(int)
    
    # Get unique clients (one row per client)
    # For clients with multiple accounts, use the account with the highest balance
    data = data.sort_values('balance_last', ascending=False).drop_duplicates('client_id', keep='first')
    
    print(f"\nTotal clients: {len(data)}")
    print(f"Clients with loans: {data['has_home_loan'].sum()}")
    print(f"Clients without loans: {(~data['has_home_loan'].astype(bool)).sum()}")
    
    # Split into train and test
    # For TRAIN: Remove ALL users with loans (only keep users without loans)
    # For TEST: Keep both users with and without loans
    train_without_loans = data[data['has_home_loan'] == 0].copy()
    test_data = data.copy()  # Test has both
    
    # Split test data
    np.random.seed(random_state)
    test_indices = np.random.choice(
        test_data.index, 
        size=int(len(test_data) * test_size), 
        replace=False
    )
    test_data = test_data.loc[test_indices].copy()
    
    # Split train data (only from users without loans)
    train_indices = np.random.choice(
        train_without_loans.index,
        size=int(len(train_without_loans) * (1 - test_size)),
        replace=False
    )
    train_data = train_without_loans.loc[train_indices].copy()
    
    print(f"\nTrain set: {len(train_data)} clients (all without loans)")
    print(f"Test set: {len(test_data)} clients")
    print(f"  - With loans: {test_data['has_home_loan'].sum()}")
    print(f"  - Without loans: {(~test_data['has_home_loan'].astype(bool)).sum()}")
    
    # Save to CSV
    train_path = os.path.join(processed_path, 'train_data.csv')
    test_path = os.path.join(processed_path, 'test_data.csv')
    
    train_data.to_csv(train_path, index=False)
    test_data.to_csv(test_path, index=False)
    
    print(f"\n✅ Data split complete!")
    print(f"Train data saved to: {train_path}")
    print(f"Test data saved to: {test_path}")
    
    return train_data, test_data

if __name__ == '__main__':
    train_data, test_data = split_train_test(test_size=0.3, random_state=42)

