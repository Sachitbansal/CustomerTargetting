import asyncio
import pandas as pd
import json
import os
from nats.aio.client import Client as NATS
from nats_config import NATS_SERVER, SUBJECTS, OUTPUT_PATH
from datetime import datetime

class FeatureGrabber:
    def __init__(self, output_file="client_features.csv", listen_seconds=5):
        self.nc = None
        self.output_file = os.path.join(OUTPUT_PATH, output_file)
        self.features_buffer = []
        self.listen_seconds = listen_seconds
        
        # Define output paths
        self.base_output = OUTPUT_PATH
        self.loan_features_path = os.path.join(self.base_output, "loan_features")
        self.card_features_path = os.path.join(self.base_output, "card_features")
        
        # Create directories
        os.makedirs(self.base_output, exist_ok=True)
        os.makedirs(self.loan_features_path, exist_ok=True)
        os.makedirs(self.card_features_path, exist_ok=True)
        
        # Load constraints and rejected lists
        self.loan_constraints = self.load_loan_constraints()
        self.loan_rejected = self.load_rejected_list('loan_rejected.csv')
        self.card_rejected = self.load_rejected_list('card_rejected.csv')

    def load_loan_constraints(self):
        """Load loan constraints from JSON file"""
        try:
            with open('loan_constraints.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("⚠ loan_constraints.json not found. Using default constraints.")
            return {
                "home_loan": {
                    "min_age": 25,
                    "max_age": 60,
                    "min_balance": 50000,
                    "min_income": 35000,
                    "employment_required": "yes",
                    "previous_default": "no"
                },
                "car_loan": {
                    "min_age": 21,
                    "max_age": 65,
                    "min_balance": 20000,
                    "min_income": 25000,
                    "employment_required": "yes",
                    "previous_default": "no"
                },
                "personal_loan": {
                    "min_age": 21,
                    "max_age": 65,
                    "min_balance": 10000,
                    "min_income": 20000,
                    "employment_required": "yes",
                    "previous_default": "no"
                },
                "business_loan": {
                    "min_age": 25,
                    "max_age": 65,
                    "min_balance": 100000,
                    "min_income": 50000,
                    "employment_required": "yes",
                    "previous_default": "no"
                }
            }

    def load_rejected_list(self, filename):
        """Load rejected client IDs from CSV"""
        try:
            filepath = os.path.join(self.base_output, filename)
            df = pd.read_csv(filepath)
            return set(df['client_id'].tolist())
        except FileNotFoundError:
            print(f"⚠ {filename} not found. No rejected clients loaded.")
            return set()

    def calculate_age(self, birth_number):
        """Calculate age from birth number (assuming format: YYMMDD)"""
        try:
            # Extract year from birth number
            year_prefix = str(birth_number)[:2]
            year = int(year_prefix)
            # Assume 19xx for years >= 50, 20xx for years < 50
            full_year = 1900 + year if year >= 50 else 2000 + year
            current_year = datetime.now().year
            return current_year - full_year
        except:
            return None

    def check_loan_eligibility(self, row, loan_type):
        """Check if client is eligible for specific loan type"""
        if loan_type not in self.loan_constraints:
            return False
        
        constraints = self.loan_constraints[loan_type]
        
        # Calculate age
        age = self.calculate_age(row.get('birth_number'))
        if age is None:
            return False
        
        # Check age constraints
        if age < constraints['min_age'] or age > constraints['max_age']:
            return False
        
        # Check balance
        balance_mean = row.get('balance_mean', 0)
        if balance_mean < constraints['min_balance']:
            return False
        
        # Check income (use avg_incoming as proxy)
        income = row.get('avg_incoming', 0)
        if income < constraints['min_income']:
            return False
        
        # Check if client is in rejected list
        if row.get('client_id') in self.loan_rejected:
            return False
        
        return True

    def check_card_eligibility(self, row, card_type):
        """Check if client is eligible for specific card type"""
        # Simple eligibility based on balance and transaction history
        balance_mean = row.get('balance_mean', 0)
        num_transactions = row.get('total_transactions', 0)
        
        # Check if client is in rejected list
        if row.get('client_id') in self.card_rejected:
            return False
        
        # Define card-specific criteria
        if card_type == 'gold_card':
            return balance_mean >= 50000 and num_transactions >= 50
        elif card_type == 'classic_card':
            return balance_mean >= 10000 and num_transactions >= 10
        elif card_type == 'junior_card':
            age = self.calculate_age(row.get('birth_number'))
            return age is not None and age < 25
        
        return False

    async def connect(self):
        self.nc = NATS()
        await self.nc.connect(NATS_SERVER)
        print(f"✓ Connected to NATS server at {NATS_SERVER}")

    async def disconnect(self):
        if self.nc:
            await self.nc.close()
            print("✓ Disconnected from NATS")

    def process_and_save_features(self):
        """Process features and save to structured CSV files"""
        if len(self.features_buffer) == 0:
            print("No features to save.")
            return
        
        # Create DataFrame
        df = pd.DataFrame(self.features_buffer)
        if 'client_id' in df.columns:
            df = df.drop_duplicates(subset=['client_id'], keep='last')
        
        print(f"\n{'='*80}")
        print(f"Processing {len(df)} client records...")
        print(f"{'='*80}\n")
        
        # Define loan-related columns to exclude from main CSV
        loan_cols = [col for col in df.columns if 'loan' in col.lower()]
        card_cols = ['num_cards', 'num_classic_cards', 'num_junior_cards', 'num_gold_cards',
                     'gold_card', 'classic_card', 'junior_card', 'earliest_card_issue', 
                     'latest_card_issue', 'card_id']
        
        # PROCESS LOAN FEATURES
        print("Processing Loan Features...")
        self.process_loan_features(df)
        
        # PROCESS CARD FEATURES
        print("\nProcessing Card Features...")
        self.process_card_features(df)
        
        # Save main features file
        main_cols = [col for col in df.columns if col not in loan_cols + card_cols + ['loan_purpose']]
        df_main = df[main_cols]
        main_output = os.path.join(self.base_output, "client_features_main.csv")
        df_main.to_csv(main_output, index=False)
        print(f"\n✓ Saved main client features to {main_output}")
        
        print(f"\n{'='*80}")
        print("Processing Complete!")
        print(f"{'='*80}\n")

    def process_loan_features(self, df):
        """Process and save loan-related features"""
        loan_types = ['car', 'personal', 'home', 'business']
        
        # Get loan-related columns
        loan_cols = [col for col in df.columns if 'loan' in col.lower() or col == 'client_id']
        
        # Process each loan type
        for loan_type in loan_types:
            loan_col = f'{loan_type}_loan'
            if loan_col in df.columns:
                # Get clients with this loan type
                df_loan = df[df[loan_col] == 1].copy()
                
                if len(df_loan) > 0:
                    # Remove loan_purpose column
                    cols_to_save = [col for col in loan_cols if col != 'loan_purpose']
                    df_loan_final = df_loan[cols_to_save]
                    
                    output_file = os.path.join(self.loan_features_path, f"{loan_type}_loan_users.csv")
                    df_loan_final.to_csv(output_file, index=False)
                    print(f"  ✓ Saved {len(df_loan_final)} {loan_type} loan users")
        
        # Process applicable loan users (no current loans but eligible)
        df_no_loans = df[(df.get('num_loans', 0) == 0) | (pd.isna(df.get('loan_purpose')))]
        
        applicable_clients = []
        for loan_type in loan_types:
            loan_name = f'{loan_type}_loan'
            for idx, row in df_no_loans.iterrows():
                if self.check_loan_eligibility(row, loan_name):
                    client_data = row.to_dict()
                    client_data['eligible_for'] = loan_name
                    applicable_clients.append(client_data)
        
        if applicable_clients:
            df_applicable = pd.DataFrame(applicable_clients)
            # Remove loan_purpose column
            cols_to_save = [col for col in df_applicable.columns if col != 'loan_purpose']
            df_applicable = df_applicable[cols_to_save]
            
            output_file = os.path.join(self.loan_features_path, "applicable_loan_users.csv")
            df_applicable.to_csv(output_file, index=False)
            print(f"  ✓ Saved {len(df_applicable)} applicable loan users")

    def process_card_features(self, df):
        """Process and save card-related features"""
        card_types = ['gold_card', 'classic_card', 'junior_card']
        
        # Get card-related columns
        card_cols = ['client_id', 'num_cards', 'num_classic_cards', 'num_junior_cards', 
                     'num_gold_cards', 'gold_card', 'classic_card', 'junior_card', 
                     'earliest_card_issue', 'latest_card_issue', 'card_id']
        card_cols = [col for col in card_cols if col in df.columns]
        
        # Process each card type
        for card_type in card_types:
            if card_type in df.columns:
                # Get clients with this card type
                df_card = df[df[card_type] == 1].copy()
                
                if len(df_card) > 0:
                    df_card_final = df_card[card_cols]
                    output_file = os.path.join(self.card_features_path, f"{card_type}_users.csv")
                    df_card_final.to_csv(output_file, index=False)
                    print(f"  ✓ Saved {len(df_card_final)} {card_type} users")
        
        # Process applicable card users (no cards but eligible)
        df_no_cards = df[df.get('num_cards', 0) == 0]
        
        applicable_clients = []
        for card_type in card_types:
            for idx, row in df_no_cards.iterrows():
                if self.check_card_eligibility(row, card_type):
                    client_data = row[card_cols].to_dict()
                    client_data['eligible_for'] = card_type
                    applicable_clients.append(client_data)
        
        if applicable_clients:
            df_applicable = pd.DataFrame(applicable_clients)
            output_file = os.path.join(self.card_features_path, "applicable_card_users.csv")
            df_applicable.to_csv(output_file, index=False)
            print(f"  ✓ Saved {len(df_applicable)} applicable card users")

    async def fetch_snapshot(self):
        subject = SUBJECTS['client_features']
        print(f"Subscribing to {subject} for {self.listen_seconds} seconds...")

        async def message_handler(msg):
            data = json.loads(msg.data.decode())
            self.features_buffer.append(data)
            print(f"[FEATURES] Received feature (total buffer: {len(self.features_buffer)})")

        sid = await self.nc.subscribe(subject, cb=message_handler)
        await asyncio.sleep(self.listen_seconds)
        print("✓ Stopped subscription.")

    async def run(self):
        print("="*80)
        print("ENHANCED FEATURE SNAPSHOT - STRUCTURED CSV OUTPUT")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"NATS Server: {NATS_SERVER}")
        print(f"Output directory: {self.base_output}")
        print(f"Listening for {self.listen_seconds} seconds for available feature messages.")
        print("="*80 + "\n")
        
        await self.connect()
        await self.fetch_snapshot()
        self.process_and_save_features()
        await self.disconnect()

async def main():
    grabber = FeatureGrabber(listen_seconds=20)
    await grabber.run()

if __name__ == "__main__":
    asyncio.run(main())