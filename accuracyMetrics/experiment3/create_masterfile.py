# create_masterfile_v2.py

import pandas as pd
import os

# --- Configuration ---
TRAIN_FILE = 'initial_training_data.csv'
STREAM_FILE = 'streaming_customers_initial_state.csv'
OUTPUT_FILE = 'MASTERFILE.csv'

def initialize_masterfile_with_new_columns():
    """
    Combines training and streaming data and initializes the 8 new columns
    required for the granular, multi-stream marketing architecture.
    """
    # 1. --- Check for required input files ---
    print("Checking for required input files...")
    if not os.path.exists(TRAIN_FILE) or not os.path.exists(STREAM_FILE):
        print(f"Error: Make sure '{TRAIN_FILE}' and '{STREAM_FILE}' exist.")
        print("Please run generate_data.py and then split_data.py first.")
        return

    # 2. --- Load the datasets ---
    print(f"Loading data from '{TRAIN_FILE}' and '{STREAM_FILE}'...")
    train_df = pd.read_csv(TRAIN_FILE)
    stream_df = pd.read_csv(STREAM_FILE)
    print(f"Loaded {len(train_df)} training and {len(stream_df)} streaming customers.")

    # 3. --- Combine into a single dataframe ---
    print("Combining datasets...")
    master_df = pd.concat([train_df, stream_df], ignore_index=True)
    
    # 4. --- Initialize the 8 New Columns ---
    print("Initializing 8 new columns for the streaming architecture...")

    # Initialize all four volume trackers to 0.0 (as float)
    master_df['volTransLastStreamed_home'] = 0.0
    master_df['volTransLastStreamed_car'] = 0.0
    master_df['volTransLastStreamed_elss'] = 0.0
    master_df['volTransLastStreamed_nifty50'] = 0.0
    print("  - Initialized 4 'volTransLastStreamed_*' columns to 0.0")

    # Initialize all four cooldown trackers to 'never'
    master_df['last_reach_out_home_loan'] = 'never'
    master_df['last_reach_out_car_loan'] = 'never'
    master_df['last_reach_out_nifty50'] = 'never'
    master_df['last_reach_out_elss'] = 'never'
    print("  - Initialized 4 'last_reach_out_*' columns to 'never'")

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
        
    # Verify a couple of the new columns to be sure
    if master_df['volTransLastStreamed_home'].sum() == 0.0:
        print("  - Verified 'volTransLastStreamed_home' is all zeros. OK.")
    else:
        print("  - ERROR: 'volTransLastStreamed_home' column has non-zero values!")

    if (master_df['last_reach_out_car_loan'] == 'never').all():
         print("  - Verified 'last_reach_out_car_loan' is all 'never'. OK.")
    else:
        print("  - ERROR: 'last_reach_out_car_loan' has values other than 'never'!")

    # 6. --- Save the final master file ---
    print(f"\nSaving the final master file to '{OUTPUT_FILE}'...")
    master_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Successfully created '{OUTPUT_FILE}' with the required architecture columns.")


if __name__ == '__main__':
    initialize_masterfile_with_new_columns()