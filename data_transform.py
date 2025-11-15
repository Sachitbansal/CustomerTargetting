"""
Comprehensive Data Transformation Pipeline
Creates client_features.csv with all required features from present_tables
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

# Configuration
PRESENT_TABLES_PATH = "data/present_tables"
OUTPUT_PATH = "data/pathway_output"
CZK_TO_USD = 0.038

os.makedirs(OUTPUT_PATH, exist_ok=True)

print("="*80)
print("DATA TRANSFORMATION PIPELINE")
print("="*80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Source: {PRESENT_TABLES_PATH}/")
print(f"Output: {OUTPUT_PATH}/")
print("="*80 + "\n")

# === LOAD DATA ===
print("Loading data from present_tables...")

client_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/client.csv")
account_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/account.csv")
disp_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/disp.csv")
trans_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/trans.csv")
loan_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/loan.csv")
order_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/order.csv")
card_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/card.csv")
district_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/district.csv")
loan_labels_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/loan_labels.csv")
card_labels_df = pd.read_csv(f"{PRESENT_TABLES_PATH}/card_labels.csv")

print(f"✓ Loaded {len(client_df)} clients")
print(f"✓ Loaded {len(trans_df)} transactions")
print(f"✓ Loaded {len(loan_df)} loans")
print(f"✓ Loaded {len(order_df)} orders")
print(f"✓ Loaded {len(card_df)} cards\n")

# === CONVERT TO USD ===
print("Converting amounts to USD...")
trans_df['amount'] = trans_df['amount'] * CZK_TO_USD
trans_df['balance'] = trans_df['balance'] * CZK_TO_USD
loan_df['amount'] = loan_df['amount'] * CZK_TO_USD
loan_df['payments'] = loan_df['payments'] * CZK_TO_USD
order_df['amount'] = order_df['amount'] * CZK_TO_USD
print("✓ Conversion complete\n")

# === TRANSACTION FEATURES ===
print("Computing transaction features...")

# Separate incoming and outgoing transactions
trans_df['is_incoming'] = trans_df['type'] == 'PRIJEM'
trans_df['is_outgoing'] = trans_df['type'] == 'VYDAJ'
trans_df['incoming_amount'] = trans_df['amount'].where(trans_df['is_incoming'], 0)
trans_df['outgoing_amount'] = trans_df['amount'].where(trans_df['is_outgoing'], 0)

# Group by account_id
trans_stats = trans_df.groupby('account_id').agg(
    total_transactions=('trans_id', 'count'),
    num_incoming=('is_incoming', 'sum'),
    num_outgoing=('is_outgoing', 'sum'),
    total_incoming=('incoming_amount', 'sum'),
    total_outgoing=('outgoing_amount', 'sum'),
    avg_incoming=('incoming_amount', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    avg_outgoing=('outgoing_amount', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    median_incoming=('incoming_amount', lambda x: x[x > 0].median() if (x > 0).any() else 0),
    median_outgoing=('outgoing_amount', lambda x: x[x > 0].median() if (x > 0).any() else 0),
    std_incoming=('incoming_amount', lambda x: x[x > 0].std() if (x > 0).any() else 0),
    std_outgoing=('outgoing_amount', lambda x: x[x > 0].std() if (x > 0).any() else 0),
    max_incoming=('incoming_amount', 'max'),
    max_outgoing=('outgoing_amount', 'max'),
    min_incoming=('incoming_amount', lambda x: x[x > 0].min() if (x > 0).any() else 0),
    min_outgoing=('outgoing_amount', lambda x: x[x > 0].min() if (x > 0).any() else 0),
    balance_min=('balance', 'min'),
    balance_max=('balance', 'max'),
    balance_mean=('balance', 'mean'),
    balance_median=('balance', 'median'),
    balance_std=('balance', 'std'),
    unique_k_symbols=('k_symbol', 'nunique'),
    unique_operations=('operation', 'nunique'),
    unique_banks=('bank', 'nunique'),
    first_transaction_date=('date', 'min'),
    last_transaction_date=('date', 'max'),
).reset_index()

# Fill NaN with 0
trans_stats = trans_stats.fillna(0)

# Compute derived features
trans_stats['net_cashflow'] = trans_stats['total_incoming'] - trans_stats['total_outgoing']
trans_stats['incoming_outgoing_ratio'] = trans_stats['total_incoming'] / (trans_stats['total_outgoing'] + 1)
trans_stats['avg_transaction_amount'] = (trans_stats['total_incoming'] + trans_stats['total_outgoing']) / (trans_stats['total_transactions'] + 1)
trans_stats['balance_volatility'] = trans_stats['balance_std'] / (trans_stats['balance_mean'].abs() + 1)
trans_stats['incoming_volatility'] = trans_stats['std_incoming'] / (trans_stats['avg_incoming'] + 1)
trans_stats['outgoing_volatility'] = trans_stats['std_outgoing'] / (trans_stats['avg_outgoing'] + 1)
trans_stats['max_to_avg_incoming_ratio'] = trans_stats['max_incoming'] / (trans_stats['avg_incoming'] + 1)
trans_stats['max_to_avg_outgoing_ratio'] = trans_stats['max_outgoing'] / (trans_stats['avg_outgoing'] + 1)

# Calculate transaction span in days
trans_stats['transaction_span_days'] = pd.to_datetime(trans_stats['last_transaction_date'], format='%y%m%d', errors='coerce') - pd.to_datetime(trans_stats['first_transaction_date'], format='%y%m%d', errors='coerce')
trans_stats['transaction_span_days'] = trans_stats['transaction_span_days'].dt.days.fillna(0)
trans_stats['transaction_frequency'] = trans_stats['total_transactions'] / (trans_stats['transaction_span_days'] + 1)

print(f"✓ Computed transaction features for {len(trans_stats)} accounts\n")

# === LOAN FEATURES ===
print("Computing loan features...")

loan_stats = loan_df.groupby('account_id').agg(
    num_loans=('loan_id', 'count'),
    loan_amount_total_usd=('amount', 'sum'),
    loan_amount_avg_usd=('amount', 'mean'),
    loan_amount_max_usd=('amount', 'max'),
    loan_amount_min_usd=('amount', 'min'),
    loan_duration_avg=('duration', 'mean'),
    loan_duration_max=('duration', 'max'),
    loan_duration_min=('duration', 'min'),
    loan_payment_avg_usd=('payments', 'mean'),
    loan_payment_max_usd=('payments', 'max'),
    loan_payment_min_usd=('payments', 'min'),
    first_loan_date=('date', 'min'),
    last_loan_date=('date', 'max'),
    loan_status_all=('status', lambda x: ','.join(x.unique())),
).reset_index()

loan_stats = loan_stats.fillna(0)

print(f"✓ Computed loan features for {len(loan_stats)} accounts\n")

# === ORDER FEATURES ===
print("Computing order features...")

order_stats = order_df.groupby('account_id').agg(
    num_orders=('order_id', 'count'),
    avg_order_amount_usd=('amount', 'mean'),
    total_order_amount_usd=('amount', 'sum'),
    max_order_amount_usd=('amount', 'max'),
    min_order_amount_usd=('amount', 'min'),
    std_order_amount_usd=('amount', 'std'),
    unique_banks_orders=('bank_to', 'nunique'),
    unique_k_symbols_orders=('k_symbol', 'nunique'),
).reset_index()

order_stats = order_stats.fillna(0)

print(f"✓ Computed order features for {len(order_stats)} accounts\n")

# === CARD FEATURES ===
print("Computing card features...")

# Join card with disp to get account_id
card_with_account = card_df.merge(disp_df[['disp_id', 'client_id', 'account_id']], on='disp_id', how='left')

# Join with card_labels to get card types
card_with_account = card_with_account.merge(card_labels_df, on=['client_id', 'account_id', 'disp_id'], how='left')
card_with_account = card_with_account.fillna(0)

# Group by client_id
card_stats = card_with_account.groupby('client_id').agg(
    num_cards=('card_id', 'count'),
    earliest_card_issue=('issued', 'min'),
    latest_card_issue=('issued', 'max'),
    num_classic_cards=('classic', 'sum'),
    num_junior_cards=('junior', 'sum'),
    num_gold_cards=('gold', 'sum'),
).reset_index()

card_stats = card_stats.fillna(0)

print(f"✓ Computed card features for {len(card_stats)} clients\n")

# === BUILD ACCOUNT-LEVEL FEATURES ===
print("Building account-level features...")

# Start with owner dispositions
owner_disp = disp_df[disp_df['type'] == 'OWNER'].copy()

# Merge with account info
account_features = owner_disp.merge(account_df, on='account_id', how='left')

# Merge with transaction stats
account_features = account_features.merge(trans_stats, on='account_id', how='left')

# Merge with loan stats
account_features = account_features.merge(loan_stats, on='account_id', how='left')

# Merge with order stats
account_features = account_features.merge(order_stats, on='account_id', how='left')

# Fill NaN values with 0 for numeric columns
numeric_cols = account_features.select_dtypes(include=[np.number]).columns
account_features[numeric_cols] = account_features[numeric_cols].fillna(0)

print(f"✓ Built features for {len(account_features)} accounts\n")

# === AGGREGATE TO CLIENT LEVEL ===
print("Aggregating to client level...")

# Group by client_id and aggregate
agg_dict = {
    'account_id': 'first',  # Keep first account_id
    'district_id': 'first',  # Keep first district_id
    'frequency': 'first',  # Keep first frequency
}

# Add all numeric transaction/loan/order columns
for col in account_features.columns:
    if col not in ['client_id', 'disp_id', 'account_id', 'district_id', 'frequency', 'type', 'date',
                   'first_transaction_date', 'last_transaction_date', 'first_loan_date', 'last_loan_date', 'loan_status_all']:
        if account_features[col].dtype in [np.float64, np.int64]:
            agg_dict[col] = 'sum'

# Special aggregations for dates and status
agg_dict['first_transaction_date'] = 'min'
agg_dict['last_transaction_date'] = 'max'
agg_dict['first_loan_date'] = 'min'
agg_dict['last_loan_date'] = 'max'
agg_dict['loan_status_all'] = lambda x: ','.join([str(s) for s in x if s != 0])

client_features = account_features.groupby('client_id').agg(agg_dict).reset_index()

# Re-calculate some averages at client level
if 'num_accounts' in client_features.columns:
    client_features['num_accounts'] = account_features.groupby('client_id').size().values
else:
    client_features.insert(3, 'num_accounts', account_features.groupby('client_id').size().values)

print(f"✓ Aggregated to {len(client_features)} clients\n")

# === JOIN WITH CLIENT BASE ===
print("Joining with client base...")

client_features = client_df.merge(client_features, on='client_id', how='left')

# Update district_id from client if missing
client_features['district_id'] = client_features['district_id_x'].fillna(client_features['district_id_y'])
client_features = client_features.drop(['district_id_x', 'district_id_y'], axis=1)

print("✓ Joined with client data\n")

# === JOIN WITH CARD FEATURES ===
print("Joining with card features...")

client_features = client_features.merge(card_stats, on='client_id', how='left')

print("✓ Joined with card data\n")

# === JOIN WITH DISTRICT INFO ===
print("Joining with district info...")

client_features = client_features.merge(district_df, left_on='district_id', right_on='A1', how='left')

print("✓ Joined with district data\n")

# === JOIN WITH LOAN LABELS (for loan purpose) ===
print("Adding loan purpose features...")

# Get loan purposes per client
loan_purpose_features = loan_labels_df.groupby('client_id').agg({
    'personal_loan': 'max',
    'car_loan': 'max',
    'home_loan': 'max',
    'credit_card_loan': 'max',
    'business_loan': 'max',
}).reset_index()

client_features = client_features.merge(loan_purpose_features, on='client_id', how='left')

print("✓ Added loan purpose features\n")

# === ADD CARD TYPE BINARY FEATURES ===
print("Adding card type features...")

# Create binary features for card types (already have counts, now add binary)
client_features['classic_card'] = (client_features['num_classic_cards'] > 0).astype(int)
client_features['gold_card'] = (client_features['num_gold_cards'] > 0).astype(int)
client_features['junior_card'] = (client_features['num_junior_cards'] > 0).astype(int)

print("✓ Added card type features\n")

# === GET ADDITIONAL IDS ===
print("Adding ID references...")

# Get first card_id, loan_id, order_id, trans_id for each client
id_features = owner_disp[['client_id', 'account_id']].copy()

# Card IDs
card_ids = card_with_account.groupby('client_id')['card_id'].first().reset_index()
id_features = id_features.merge(card_ids, on='client_id', how='left')

# Loan IDs
loan_ids = loan_df.merge(owner_disp[['account_id', 'client_id']], on='account_id').groupby('client_id')['loan_id'].first().reset_index()
id_features = id_features.merge(loan_ids, on='client_id', how='left')

# Order IDs
order_ids = order_df.merge(owner_disp[['account_id', 'client_id']], on='account_id').groupby('client_id')['order_id'].first().reset_index()
id_features = id_features.merge(order_ids, on='client_id', how='left')

# Transaction IDs
trans_ids = trans_df.merge(owner_disp[['account_id', 'client_id']], on='account_id').groupby('client_id')['trans_id'].first().reset_index()
id_features = id_features.merge(trans_ids, on='client_id', how='left')

# Keep only unique client_ids
id_features = id_features.groupby('client_id').first().reset_index()

# Merge with client_features
client_features = client_features.merge(id_features[['client_id', 'card_id', 'loan_id', 'order_id', 'trans_id']],
                                       on='client_id', how='left')

print("✓ Added ID references\n")

# === REMOVE DUPLICATES ===
print("Removing duplicates...")

# Check for duplicates
duplicates = client_features[client_features.duplicated(subset=['client_id'], keep=False)]
if len(duplicates) > 0:
    print(f"⚠ Found {len(duplicates)} duplicate client records, keeping first occurrence")
    client_features = client_features.drop_duplicates(subset=['client_id'], keep='first')

print(f"✓ Ensured unique clients: {len(client_features)} rows\n")

# === FILL REMAINING NaN VALUES ===
print("Filling missing values...")

# Fill numeric columns with 0
numeric_cols = client_features.select_dtypes(include=[np.number]).columns
client_features[numeric_cols] = client_features[numeric_cols].fillna(0)

# Fill string columns with empty string
string_cols = client_features.select_dtypes(include=[object]).columns
for col in string_cols:
    if col not in ['birth_number', 'frequency', 'loan_status_all']:
        client_features[col] = client_features[col].fillna('')

print("✓ Filled missing values\n")

# === REORDER COLUMNS TO MATCH EXPECTED FORMAT ===
print("Reordering columns...")

# Define column order based on user's requirements
column_order = [
    'client_id', 'birth_number', 'district_id', 'num_accounts',
    'total_transactions', 'num_incoming', 'num_outgoing',
    'total_incoming', 'total_outgoing', 'avg_incoming', 'avg_outgoing',
    'median_incoming', 'median_outgoing', 'std_incoming', 'std_outgoing',
    'max_incoming', 'max_outgoing', 'min_incoming', 'min_outgoing',
    'balance_min', 'balance_max', 'balance_mean', 'balance_median', 'balance_std',
    'unique_k_symbols', 'unique_operations', 'unique_banks', 'transaction_span_days',
    'net_cashflow', 'incoming_outgoing_ratio', 'avg_transaction_amount',
    'transaction_frequency', 'balance_volatility', 'incoming_volatility', 'outgoing_volatility',
    'max_to_avg_incoming_ratio', 'max_to_avg_outgoing_ratio',
    'num_loans', 'loan_amount_total_usd', 'loan_amount_avg_usd',
    'loan_amount_max_usd', 'loan_amount_min_usd',
    'loan_duration_avg', 'loan_duration_max', 'loan_duration_min',
    'loan_payment_avg_usd', 'loan_payment_max_usd', 'loan_payment_min_usd',
    'num_orders', 'avg_order_amount_usd', 'total_order_amount_usd',
    'max_order_amount_usd', 'min_order_amount_usd', 'std_order_amount_usd',
    'unique_banks_orders', 'unique_k_symbols_orders',
    'loan_status_all', 'frequency',
    'first_transaction_date', 'last_transaction_date',
    'first_loan_date', 'last_loan_date',
    'account_id', 'card_id', 'loan_id', 'order_id', 'trans_id',
    'num_cards', 'earliest_card_issue', 'latest_card_issue',
    'num_classic_cards', 'num_junior_cards', 'num_gold_cards',
    'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16',
    'personal_loan', 'car_loan', 'home_loan', 'credit_card_loan', 'business_loan',
    'classic_card', 'gold_card', 'junior_card'
]

# Keep only columns that exist and add missing ones
available_cols = [col for col in column_order if col in client_features.columns]
client_features_final = client_features[available_cols].copy()

print("✓ Reordered columns\n")

# === SAVE OUTPUT ===
print("Saving output...")

output_file = f"{OUTPUT_PATH}/client_features.csv"
client_features_final.to_csv(output_file, index=False)

print(f"✓ Saved client_features.csv with {len(client_features_final)} rows and {len(client_features_final.columns)} columns\n")

# === SUMMARY STATISTICS ===
print("="*80)
print("SUMMARY STATISTICS")
print("="*80)
print(f"Total clients: {len(client_features_final)}")
print(f"Total features: {len(client_features_final.columns)}")
print(f"\nClients with transactions: {(client_features_final['total_transactions'] > 0).sum()}")
print(f"Clients with loans: {(client_features_final['num_loans'] > 0).sum()}")
print(f"Clients with orders: {(client_features_final['num_orders'] > 0).sum()}")
print(f"Clients with cards: {(client_features_final['num_cards'] > 0).sum()}")
print("\nNull value counts:")
print(client_features_final.isnull().sum()[client_features_final.isnull().sum() > 0])
print("="*80)
print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

print(f"\nOutput saved to: {output_file}")
print("Pipeline complete!")
