# create_masterfile.py

import pandas as pd
import os

# --- Configuration ---
TRAIN_FILE = 'initial_training_data.csv'
STREAM_FILE = 'streaming_customers_initial_state.csv'
OUTPUT_FILE = 'MASTERFILE.csv'

# These are the columns that will be "reset" to 0 for the streaming customers
TARGET_COLUMNS = ['opted_home_loan', 'opted_car_loan', 'recommend_nifty50', 'recommend_elss']

def create_combined_masterfile():
    """
    Combines the initial training data with the streaming customer data.
    The streaming data's target columns are set to 0 to simulate a state
    before any recommendations have been made or accepted.
    """
    # 1. --- Check for required input files ---
    print("Checking for required input files...")
    if not os.path.exists(TRAIN_FILE) or not os.path.exists(STREAM_FILE):
        print(f"Error: Make sure '{TRAIN_FILE}' and '{STREAM_FILE}' exist in the current directory.")
        print("Please run generate_data.py and then split_data.py first.")
        return

    # 2. --- Load the datasets ---
    print(f"Loading training data from '{TRAIN_FILE}'...")
    train_df = pd.read_csv(TRAIN_FILE)
    print(f"Loaded {len(train_df)} training customers.")

    print(f"Loading streaming data from '{STREAM_FILE}'...")
    stream_df = pd.read_csv(STREAM_FILE)
    print(f"Loaded {len(stream_df)} streaming customers.")

    # 3. --- Modify the streaming data ---
    print(f"Setting target columns {TARGET_COLUMNS} to 0 for the streaming data...")
    
    # A quick check to ensure the target columns exist before modification
    for col in TARGET_COLUMNS:
        if col not in stream_df.columns:
            print(f"Warning: Target column '{col}' not found in '{STREAM_FILE}'. Skipping.")
            continue
        # Set the column to 0
        stream_df[col] = 0
        
    print("Modification complete.")
    print("Original target value counts in streaming data (before reset):")
    # This just reads the file again to show the original state for verification
    temp_df = pd.read_csv(STREAM_FILE)
    print(temp_df[TARGET_COLUMNS].sum())


    # 4. --- Combine the two dataframes ---
    print("\nCombining the two datasets...")
    # The training data comes first, followed by the modified streaming data
    master_df = pd.concat([train_df, stream_df], ignore_index=True)
    
    # 5. --- Verification ---
    print("\nVerifying the combined master file...")
    expected_rows = len(train_df) + len(stream_df)
    actual_rows = len(master_df)
    print(f"  - Expected total rows: {expected_rows}")
    print(f"  - Actual total rows in master file: {actual_rows}")
    if expected_rows != actual_rows:
        print("  - ERROR: Row count mismatch!")
    else:
        print("  - Row count matches. OK.")
        
    # Verify that the last N rows (the streaming part) have 0s in target columns
    streaming_part_in_master = master_df.tail(len(stream_df))
    targets_sum = streaming_part_in_master[TARGET_COLUMNS].sum().sum()
    if targets_sum == 0:
        print(f"  - Verified that all {len(stream_df)} streaming customers have target values of 0. OK.")
    else:
        print("  - ERROR: Streaming customers in the master file have non-zero target values!")

    # 6. --- Save the final master file ---
    print(f"\nSaving the combined data to '{OUTPUT_FILE}'...")
    master_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Successfully created '{OUTPUT_FILE}'.")


if __name__ == '__main__':
    create_combined_masterfile()