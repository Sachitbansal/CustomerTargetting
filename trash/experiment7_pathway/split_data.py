# split_data.py

import pandas as pd
import numpy as np
from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit
import os

# --- Configuration ---
MASTER_CUSTOMER_FILE = 'customers_master_multi_product.csv'
MASTER_TRANSACTION_FILE = 'transactions_history_categorized.csv'
TARGET_COLUMNS = ['opted_home_loan', 'opted_car_loan', 'recommend_nifty50', 'recommend_elss']

TRAIN_SIZE = 10000
STREAM_SIZE = 2500
TOTAL_SIZE = TRAIN_SIZE + STREAM_SIZE

# --- Output Filenames ---
TRAIN_CUSTOMERS_OUTPUT = 'initial_training_data.csv'
STREAM_CUSTOMERS_OUTPUT = 'streaming_customers_initial_state.csv'
STREAM_TRANSACTIONS_OUTPUT = 'streaming_transactions.csv'

def perform_iterative_stratified_split():
    """
    Loads the master data, performs a multi-label iterative stratified split,
    and saves the three required files for the streaming experiment.
    This method is robust against rare label combinations.
    """
    # 1. --- Load Data ---
    print("Loading master data files...")
    if not os.path.exists(MASTER_CUSTOMER_FILE) or not os.path.exists(MASTER_TRANSACTION_FILE):
        print(f"Error: Make sure '{MASTER_CUSTOMER_FILE}' and '{MASTER_TRANSACTION_FILE}' exist.")
        print("Please run generate_data.py first.")
        return

    customers_df = pd.read_csv(MASTER_CUSTOMER_FILE)
    transactions_df = pd.read_csv(MASTER_TRANSACTION_FILE)
    
    if len(customers_df) != TOTAL_SIZE:
        print(f"Error: The customer file has {len(customers_df)} rows, but {TOTAL_SIZE} are needed for the split.")
        print(f"Please set NUM_CUSTOMERS = {TOTAL_SIZE} in generate_data.py and run it again.")
        return
        
    print(f"Loaded {len(customers_df)} customers and {len(transactions_df)} transactions.")

    # 2. --- Perform Multi-Label Iterative Stratified Split ---
    print("Performing multi-label iterative stratified split (robust method)...")

    # The features (X) are just the indices, the labels (y) are the target columns
    X = customers_df.index.to_numpy().reshape(-1, 1)
    y = customers_df[TARGET_COLUMNS].to_numpy()

    # Calculate the test_size ratio
    split_ratio = STREAM_SIZE / TOTAL_SIZE

    # Initialize the splitter
    # n_splits=1 because we only need one split
    msss = MultilabelStratifiedShuffleSplit(n_splits=1, test_size=split_ratio, random_state=42)

    # The split method returns indices for train and test sets
    train_indices, stream_indices = next(msss.split(X, y))

    # Use the indices to select the corresponding rows from the original dataframe
    train_customers_df = customers_df.iloc[train_indices].copy()
    stream_customers_df = customers_df.iloc[stream_indices].copy()

    print(f"Split complete. Training set size: {len(train_customers_df)}, Streaming set size: {len(stream_customers_df)}")
    
    print("\nVerifying stratification for all target columns:")
    for col in TARGET_COLUMNS:
        original_ratio = customers_df[col].mean()
        train_ratio = train_customers_df[col].mean()
        stream_ratio = stream_customers_df[col].mean()
        print(f"  - {col}:")
        print(f"    Original: {original_ratio:.4f} | Train: {train_ratio:.4f} | Stream: {stream_ratio:.4f}")

    # 3. --- Filter Transactions for the Streaming Set ---
    print("\nFiltering transactions for the streaming customers...")
    
    streaming_customer_ids = set(stream_customers_df['customer_id'])
    streaming_transactions_df = transactions_df[transactions_df['customer_id'].isin(streaming_customer_ids)]
    
    print(f"Found {len(streaming_transactions_df)} transactions for the {len(stream_customers_df)} streaming customers.")

    # 4. --- Save the Output Files ---
    print("\nSaving the three output CSV files...")

    train_customers_df.to_csv(TRAIN_CUSTOMERS_OUTPUT, index=False)
    print(f"  -> Saved '{TRAIN_CUSTOMERS_OUTPUT}'")

    stream_customers_df.to_csv(STREAM_CUSTOMERS_OUTPUT, index=False)
    print(f"  -> Saved '{STREAM_CUSTOMERS_OUTPUT}'")
    
    streaming_transactions_df.to_csv(STREAM_TRANSACTIONS_OUTPUT, index=False)
    print(f"  -> Saved '{STREAM_TRANSACTIONS_OUTPUT}'")
    
    print("\nProcess finished successfully!")


if __name__ == '__main__':
    perform_iterative_stratified_split()