# add_streaming_columns.py

import pandas as pd
import os

# --- Configuration ---
MASTER_FILE = 'MASTERFILE.csv'

# Define the new columns and their default values
COLUMNS_TO_ADD = {
'last_update_timestamp': '1970-01-01T00:00:00'
}

def add_columns_to_masterfile():
    """
    Loads an existing MASTERFILE.csv, adds the 8 required streaming/cooldown
    columns if they don't already exist, and saves the file back in place.
    This script is safe to run multiple times.
    """
    # 1. --- Check if the master file exists ---
    if not os.path.exists(MASTER_FILE):
        print(f"Error: The file '{MASTER_FILE}' was not found.")
        print("Please ensure you have created the master file first.")
        return

    try:
        # 2. --- Load the existing CSV ---
        print(f"Loading existing data from '{MASTER_FILE}'...")
        df = pd.read_csv(MASTER_FILE)
        print(f"Loaded {len(df)} customer records.")

        # 3. --- Add new columns one by one, checking for existence first ---
        print("\nChecking for and adding required streaming columns...")
        
        columns_were_added = False
        for col_name, default_value in COLUMNS_TO_ADD.items():
            if col_name not in df.columns:
                print(f"  - Adding column: '{col_name}' with default value '{default_value}'")
                df[col_name] = default_value
                columns_were_added = True
            else:
                print(f"  - Column '{col_name}' already exists. Skipping.")

        # 4. --- Save the file only if changes were made ---
        if columns_were_added:
            print(f"\nSaving updated data back to '{MASTER_FILE}'...")
            df.to_csv(MASTER_FILE, index=False)
            print("Successfully updated the master file with new columns.")
            
            # Optional: Display the first few rows with new columns for verification
            print("\nVerification: Displaying header and first 2 rows of the updated file:")
            print(df.head(2))
        else:
            print("\nNo new columns needed to be added. The file is already up to date.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please check that the CSV file is not corrupted.")

if __name__ == '__main__':
    add_columns_to_masterfile()