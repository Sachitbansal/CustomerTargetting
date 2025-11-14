import pandas as pd
import os
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

# Define paths
RAW_DATA_PATH = "data/raw"
OUTPUT_PATH = "data/csv_tables"

def create_loan_labels():
    """
    Create loan_labels.csv with client_id, account_id, disp_id, loan_purpose, and loan type columns
    """
    print("Creating loan_labels.csv...")

    # Load required files
    loan = pd.read_csv(os.path.join(RAW_DATA_PATH, "loan.asc"), sep=';', quotechar='"', dtype=str)
    disp = pd.read_csv(os.path.join(RAW_DATA_PATH, "disp.asc"), sep=';', quotechar='"', dtype=str)

    # Load master dataset with loan purpose (if exists)
    master_file = "master_with_loan_purpose.csv"
    us_loans_file = "loans_types_data.csv"

    # Clean column names
    loan.columns = loan.columns.str.strip()
    disp.columns = disp.columns.str.strip()

    # Merge loan with disp on account_id to get client_id and disp_id
    # Only keep OWNER relationships
    loan_labels = loan.merge(
        disp[disp['type'] == 'OWNER'],
        on='account_id',
        how='left'
    )

    # Select base columns
    loan_labels = loan_labels[['client_id', 'account_id', 'disp_id']]

    # Try to match with master dataset to get loan purpose
    if os.path.exists(master_file):
        print(f"  Loading master dataset from {master_file}...")
        master = pd.read_csv(master_file, low_memory=False)

        # Convert account_id to string for consistent merging
        master['account_id'] = master['account_id'].astype(str)

        # Merge to get loan_purpose
        loan_labels = loan_labels.merge(
            master[['account_id', 'loan_purpose']].drop_duplicates('account_id'),
            on='account_id',
            how='left'
        )
    elif os.path.exists(us_loans_file):
        print(f"  Matching loan purposes using {us_loans_file}...")
        loan_labels = match_loan_purposes(loan_labels, us_loans_file)
    else:
        print("  Warning: No loan purpose data found. Creating default loan_purpose...")
        loan_labels['loan_purpose'] = 'unknown'

    # Classify loan purposes into loan types
    loan_labels = classify_loan_types(loan_labels)

    # Save to CSV file
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    output_file = os.path.join(OUTPUT_PATH, "loan_labels.csv")
    loan_labels.to_csv(output_file, index=False)
    print(f"✅ Saved loan_labels.csv with {len(loan_labels)} rows")
    print(f"   Columns: {loan_labels.columns.tolist()}")

    # Display loan type distribution
    print(f"\n   Loan Type Distribution:")
    print(f"   - Personal Loan: {loan_labels['personal_loan'].sum()}")
    print(f"   - Car Loan: {loan_labels['car_loan'].sum()}")
    print(f"   - Home Loan: {loan_labels['home_loan'].sum()}")
    print(f"   - Credit Card Loan: {loan_labels['credit_card_loan'].sum()}")
    print(f"   - Business Loan: {loan_labels['business_loan'].sum()}")

    return loan_labels


def match_loan_purposes(loan_labels, us_loans_file):
    """
    Match loan purposes from US dataset using nearest neighbors approach
    (Based on notebook cell 23 approach)
    """
    try:
        # Load master features dataset
        czech_file = "enhanced_client_features_with_ids_and_cardstats_usd.csv"
        if not os.path.exists(czech_file):
            print(f"  Warning: {czech_file} not found. Using default loan purpose.")
            loan_labels['loan_purpose'] = 'unknown'
            return loan_labels

        # Load datasets
        czech = pd.read_csv(czech_file, low_memory=False)
        us = pd.read_csv(us_loans_file, low_memory=False)

        # Select comparable features (as per notebook)
        czech_features = [
            'balance_mean', 'total_incoming', 'total_outgoing',
            'loan_amount_total_usd', 'loan_payment_avg_usd',
            'loan_duration_avg', 'num_loans', 'num_cards', 'net_cashflow'
        ]
        us_features = [
            'annual_income', 'total_credit_utilized',
            'loan_amount', 'installment', 'term',
            'num_mort_accounts', 'num_total_cc_accounts',
            'debt_to_income'
        ]

        # Ensure all features exist
        czech_features = [f for f in czech_features if f in czech.columns]
        us_features = [f for f in us_features if f in us.columns]

        # Clean and normalize
        czech_scaled = StandardScaler().fit_transform(czech[czech_features].fillna(0))
        us_scaled = StandardScaler().fit_transform(us[us_features].fillna(0))

        # Find nearest US record for each Czech client
        nbrs = NearestNeighbors(n_neighbors=3, metric='euclidean').fit(us_scaled)
        distances, indices = nbrs.kneighbors(czech_scaled)

        # Map purposes (take first neighbor)
        czech['loan_purpose'] = us.iloc[indices[:, 0]]['loan_purpose'].values

        # Merge with loan_labels based on account_id
        loan_labels = loan_labels.merge(
            czech[['account_id', 'loan_purpose']].drop_duplicates('account_id'),
            on='account_id',
            how='left'
        )

        # Fill any remaining nulls
        loan_labels['loan_purpose'] = loan_labels['loan_purpose'].fillna('unknown')

    except Exception as e:
        print(f"  Error matching loan purposes: {e}")
        loan_labels['loan_purpose'] = 'unknown'

    return loan_labels


def classify_loan_types(df):
    """
    Classify loan_purpose into binary columns for each loan type:
    - personal_loan
    - car_loan
    - home_loan
    - credit_card_loan
    - business_loan
    """
    # Initialize all loan type columns to 0
    df['personal_loan'] = 0
    df['car_loan'] = 0
    df['home_loan'] = 0
    df['credit_card_loan'] = 0
    df['business_loan'] = 0

    # Classify based on loan_purpose
    # Personal loans
    personal_keywords = ['debt_consolidation', 'medical', 'vacation', 'wedding', 'other', 'moving']
    df.loc[df['loan_purpose'].isin(personal_keywords), 'personal_loan'] = 1

    # Car loans
    car_keywords = ['car']
    df.loc[df['loan_purpose'].isin(car_keywords), 'car_loan'] = 1

    # Home loans (mortgage, home improvement, major purchase)
    home_keywords = ['home_improvement', 'house', 'major_purchase', 'home']
    df.loc[df['loan_purpose'].isin(home_keywords), 'home_loan'] = 1

    # Credit card loans
    credit_card_keywords = ['credit_card']
    df.loc[df['loan_purpose'].isin(credit_card_keywords), 'credit_card_loan'] = 1

    # Business loans
    business_keywords = ['small_business', 'business', 'renewable_energy']
    df.loc[df['loan_purpose'].isin(business_keywords), 'business_loan'] = 1

    return df


def create_card_labels():
    """
    Create card_labels.csv with client_id, account_id, disp_id,
    and boolean columns for classic and gold cards
    """
    print("\nCreating card_labels.csv...")

    # Load required files
    card = pd.read_csv(os.path.join(RAW_DATA_PATH, "card.asc"), sep=';', quotechar='"', dtype=str)
    disp = pd.read_csv(os.path.join(RAW_DATA_PATH, "disp.asc"), sep=';', quotechar='"', dtype=str)

    # Clean column names
    card.columns = card.columns.str.strip()
    disp.columns = disp.columns.str.strip()

    # Merge card with disp to get client_id and account_id
    card_with_client = card.merge(disp, on='disp_id', how='left')

    # Create boolean columns for card types
    card_with_client['classic'] = (card_with_client['type_x'] == 'classic').astype(int)
    card_with_client['gold'] = (card_with_client['type_x'] == 'gold').astype(int)
    card_with_client['junior'] = (card_with_client['type_x'] == 'junior').astype(int)

    # Group by client_id, account_id, disp_id to aggregate card types
    # In case one client has multiple cards
    card_labels = card_with_client.groupby(['client_id', 'account_id', 'disp_id'], dropna=False).agg({
        'classic': 'max',  # 1 if they have at least one classic card
        'gold': 'max',     # 1 if they have at least one gold card
        'junior': 'max'    # 1 if they have at least one junior card
    }).reset_index()

    # Save to CSV file
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    output_file = os.path.join(OUTPUT_PATH, "card_labels.csv")
    card_labels.to_csv(output_file, index=False)
    print(f"✅ Saved card_labels.csv with {len(card_labels)} rows")
    print(f"   Columns: {card_labels.columns.tolist()}")

    # Display summary statistics
    print(f"\n   Card Type Distribution:")
    print(f"   - Classic cards: {card_labels['classic'].sum()}")
    print(f"   - Gold cards: {card_labels['gold'].sum()}")
    print(f"   - Junior cards: {card_labels['junior'].sum()}")

    return card_labels


def main():
    """
    Main function to create both label files
    """
    print("="*60)
    print("Creating Label Tables")
    print("="*60)

    # Create loan labels
    loan_labels = create_loan_labels()

    # Create card labels
    card_labels = create_card_labels()

    print("\n" + "="*60)
    print("Label Tables Created Successfully!")
    print("="*60)

    # Display sample data
    print("\n📊 Sample of loan_labels.csv:")
    print(loan_labels.head())

    print("\n📊 Sample of card_labels.csv:")
    print(card_labels.head())


if __name__ == "__main__":
    main()
