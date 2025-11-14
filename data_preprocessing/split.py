import pandas as pd
import os
import shutil
import numpy as np
from pathlib import Path

# Define paths
CSV_TABLES_PATH = "data/csv_tables"
PRESENT_TABLES_PATH = "data/present_tables"
STREAM_TABLES_PATH = "data/stream_tables"

def clean_output_directories():
    """
    Remove existing present_tables and stream_tables directories and create fresh ones
    """
    print("Cleaning output directories...")

    # Remove directories if they exist
    for path in [PRESENT_TABLES_PATH, STREAM_TABLES_PATH]:
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"  Removed existing directory: {path}")

    # Create fresh directories
    os.makedirs(PRESENT_TABLES_PATH, exist_ok=True)
    os.makedirs(STREAM_TABLES_PATH, exist_ok=True)
    print(f"  Created fresh directories: {PRESENT_TABLES_PATH}, {STREAM_TABLES_PATH}")


def get_client_account_mapping():
    """
    Get mapping between clients and accounts using disp table
    """
    disp_path = os.path.join(CSV_TABLES_PATH, "disp.csv")
    if not os.path.exists(disp_path):
        return None, None

    disp = pd.read_csv(disp_path)

    # Get client to account mapping (only OWNER relationships)
    client_accounts = disp[disp['type'] == 'OWNER'][['client_id', 'account_id']].drop_duplicates()

    # Create mappings
    client_to_accounts = client_accounts.groupby('client_id')['account_id'].apply(list).to_dict()
    account_to_client = dict(zip(client_accounts['account_id'], client_accounts['client_id']))

    return client_to_accounts, account_to_client


def split_clients(split_ratio=0.85):
    """
    Split clients into present and stream groups

    Args:
        split_ratio: Percentage of clients to keep in present_tables (default 85%)

    Returns:
        Tuple of (present_clients, stream_clients)
    """
    client_path = os.path.join(CSV_TABLES_PATH, "client.csv")

    if not os.path.exists(client_path):
        print("  Warning: client.csv not found. Cannot split by clients.")
        return set(), set()

    clients = pd.read_csv(client_path)
    client_ids = clients['client_id'].unique()

    # Shuffle and split
    np.random.seed(42)  # For reproducibility
    shuffled_clients = np.random.permutation(client_ids)

    split_index = int(len(shuffled_clients) * split_ratio)
    present_clients = set(shuffled_clients[:split_index])
    stream_clients = set(shuffled_clients[split_index:])

    print(f"  Total clients: {len(client_ids)}")
    print(f"  Present clients: {len(present_clients)} ({len(present_clients)/len(client_ids)*100:.1f}%)")
    print(f"  Stream clients: {len(stream_clients)} ({len(stream_clients)/len(client_ids)*100:.1f}%)")

    return present_clients, stream_clients


def split_transactions(present_clients, account_to_client, trans_split_ratio=0.50):
    """
    Split transactions: 50% of transactions for present clients go to present_tables,
    rest go to stream_tables. All transactions for stream clients go to stream_tables.

    Args:
        present_clients: Set of client IDs in present group
        account_to_client: Mapping from account_id to client_id
        trans_split_ratio: Percentage of transactions to keep in present for present clients

    Returns:
        Tuple of (present_trans_ids, stream_trans_ids)
    """
    trans_path = os.path.join(CSV_TABLES_PATH, "trans.csv")

    if not os.path.exists(trans_path):
        return set(), set()

    trans = pd.read_csv(trans_path)

    # Add client_id to transactions
    trans['client_id'] = trans['account_id'].map(account_to_client)

    # Separate transactions by client group
    present_client_trans = trans[trans['client_id'].isin(present_clients)]
    stream_client_trans = trans[trans['client_id'].isin(present_clients) == False]

    # For present clients, split their transactions by date (earlier 50% to present)
    present_trans_ids = set()
    if len(present_client_trans) > 0:
        # Group by account and take first 50% of transactions (chronologically)
        for account_id, group in present_client_trans.groupby('account_id'):
            # Sort by date
            group_sorted = group.sort_values('date')
            split_idx = int(len(group_sorted) * trans_split_ratio)
            present_trans_ids.update(group_sorted.iloc[:split_idx]['trans_id'].values)

    # All other transactions go to stream
    stream_trans_ids = set(trans['trans_id']) - present_trans_ids

    print(f"  Total transactions: {len(trans)}")
    print(f"  Present transactions: {len(present_trans_ids)} ({len(present_trans_ids)/len(trans)*100:.1f}%)")
    print(f"  Stream transactions: {len(stream_trans_ids)} ({len(stream_trans_ids)/len(trans)*100:.1f}%)")

    return present_trans_ids, stream_trans_ids


def split_csv_file(csv_file, present_clients, present_accounts, present_trans_ids,
                    client_to_accounts, account_to_client):
    """
    Split a CSV file based on client/account/transaction membership

    Args:
        csv_file: Name of the CSV file to split
        present_clients: Set of client IDs in present group
        present_accounts: Set of account IDs in present group
        present_trans_ids: Set of transaction IDs in present group
        client_to_accounts: Mapping from client_id to list of account_ids
        account_to_client: Mapping from account_id to client_id
    """
    file_path = os.path.join(CSV_TABLES_PATH, csv_file)

    if not os.path.exists(file_path):
        print(f"  Warning: {csv_file} not found. Skipping.")
        return

    print(f"\nProcessing {csv_file}...")
    df = pd.read_csv(file_path)

    # Determine split strategy based on file type
    if csv_file == "client.csv":
        present_df = df[df['client_id'].isin(present_clients)]
        stream_df = df[df['client_id'].isin(present_clients) == False]

    elif csv_file == "account.csv":
        present_df = df[df['account_id'].isin(present_accounts)]
        stream_df = df[df['account_id'].isin(present_accounts) == False]

    elif csv_file == "disp.csv":
        present_df = df[df['account_id'].isin(present_accounts)]
        stream_df = df[df['account_id'].isin(present_accounts) == False]

    elif csv_file == "trans.csv":
        present_df = df[df['trans_id'].isin(present_trans_ids)]
        stream_df = df[df['trans_id'].isin(present_trans_ids) == False]

    elif csv_file == "loan.csv":
        present_df = df[df['account_id'].isin(present_accounts)]
        stream_df = df[df['account_id'].isin(present_accounts) == False]

    elif csv_file == "order.csv":
        present_df = df[df['account_id'].isin(present_accounts)]
        stream_df = df[df['account_id'].isin(present_accounts) == False]

    elif csv_file == "card.csv":
        # Card links to disp, so we need to get disp_ids for present accounts
        disp = pd.read_csv(os.path.join(CSV_TABLES_PATH, "disp.csv"))
        present_disp_ids = set(disp[disp['account_id'].isin(present_accounts)]['disp_id'])
        present_df = df[df['disp_id'].isin(present_disp_ids)]
        stream_df = df[df['disp_id'].isin(present_disp_ids) == False]

    elif csv_file == "loan_labels.csv":
        present_df = df[df['client_id'].isin(present_clients)]
        stream_df = df[df['client_id'].isin(present_clients) == False]

    elif csv_file == "card_labels.csv":
        present_df = df[df['client_id'].isin(present_clients)]
        stream_df = df[df['client_id'].isin(present_clients) == False]

    elif csv_file == "district.csv":
        # District is a lookup table, include all in both
        present_df = df.copy()
        stream_df = df.copy()

    else:
        # Default: split by client_id if exists, otherwise by account_id, otherwise all to present
        if 'client_id' in df.columns:
            present_df = df[df['client_id'].isin(present_clients)]
            stream_df = df[df['client_id'].isin(present_clients) == False]
        elif 'account_id' in df.columns:
            present_df = df[df['account_id'].isin(present_accounts)]
            stream_df = df[df['account_id'].isin(present_accounts) == False]
        else:
            present_df = df.copy()
            stream_df = pd.DataFrame(columns=df.columns)

    # Save split files
    present_file = os.path.join(PRESENT_TABLES_PATH, csv_file)
    stream_file = os.path.join(STREAM_TABLES_PATH, csv_file)

    present_df.to_csv(present_file, index=False)
    stream_df.to_csv(stream_file, index=False)

    print(f"  Total rows: {len(df)}")
    print(f"  Present rows: {len(present_df)} ({len(present_df)/len(df)*100:.1f}%)")
    print(f"  Stream rows: {len(stream_df)} ({len(stream_df)/len(df)*100:.1f}%)")
    print(f"  ✅ Saved to {present_file} and {stream_file}")


def main():
    """
    Main function to split all CSV files in csv_tables
    """
    print("="*70)
    print("SPLITTING CSV DATA INTO PRESENT AND STREAM TABLES")
    print("="*70)

    # Step 1: Clean output directories
    clean_output_directories()

    # Step 2: Get client-account mappings
    print("\nGetting client-account mappings...")
    client_to_accounts, account_to_client = get_client_account_mapping()

    if client_to_accounts is None:
        print("  Error: Could not create client-account mapping. Exiting.")
        return

    # Step 3: Split clients (85% present, 15% stream)
    print("\nSplitting clients...")
    present_clients, stream_clients = split_clients(split_ratio=0.85)

    # Step 4: Get present accounts
    present_accounts = set()
    for client_id in present_clients:
        if client_id in client_to_accounts:
            present_accounts.update(client_to_accounts[client_id])

    print(f"\n  Present accounts: {len(present_accounts)}")

    # Step 5: Split transactions (50% of present client transactions to present)
    print("\nSplitting transactions...")
    present_trans_ids, stream_trans_ids = split_transactions(
        present_clients, account_to_client, trans_split_ratio=0.50
    )

    # Step 6: Process all CSV files
    print("\n" + "="*70)
    print("PROCESSING CSV FILES")
    print("="*70)

    csv_files = [f for f in os.listdir(CSV_TABLES_PATH) if f.endswith('.csv')]

    for csv_file in sorted(csv_files):
        split_csv_file(
            csv_file,
            present_clients,
            present_accounts,
            present_trans_ids,
            client_to_accounts,
            account_to_client
        )

    print("\n" + "="*70)
    print("SPLIT COMPLETED SUCCESSFULLY!")
    print("="*70)
    print(f"\nPresent tables saved to: {PRESENT_TABLES_PATH}")
    print(f"Stream tables saved to: {STREAM_TABLES_PATH}")


if __name__ == "__main__":
    main()
