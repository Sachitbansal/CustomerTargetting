"""
Data Fetch - NATS-Based Real-Time Feature Calculation (Complete Version)
Extracts ALL features matching master_with_loan_purpose.csv format
"""

import asyncio
import pandas as pd
import numpy as np
import json
import os
from nats.aio.client import Client as NATS
from nats_config import NATS_SERVER, SUBJECTS, CZK_TO_USD, PRESENT_PATH
from datetime import datetime
from collections import defaultdict


class DataProcessor:
    def __init__(self):
        self.nc = None

        # In-memory data stores
        self.clients = {}
        self.accounts = {}
        self.disps = {}
        self.districts = {}
        self.transactions = defaultdict(list)
        self.loans = defaultdict(list)
        self.loan_labels = defaultdict(list)
        self.orders = defaultdict(list)
        self.cards = defaultdict(list)
        self.card_labels = defaultdict(list)

        # Statistics
        self.message_count = 0
        self.feature_calc_count = 0
        self.last_calc_time = datetime.now()
        self.calc_every_n_messages = 50

    def load_present_tables(self):
        """Load initial data from present_tables"""
        print("\nLoading initial data from present_tables...")

        try:
            # Load clients
            df = pd.read_csv(f"{PRESENT_PATH}/client.csv")
            for _, row in df.iterrows():
                self.clients[row['client_id']] = row.to_dict()
            print(f"  ✓ Loaded {len(self.clients)} clients")

            # Load accounts
            df = pd.read_csv(f"{PRESENT_PATH}/account.csv")
            for _, row in df.iterrows():
                self.accounts[row['account_id']] = row.to_dict()
            print(f"  ✓ Loaded {len(self.accounts)} accounts")

            # Load disps
            df = pd.read_csv(f"{PRESENT_PATH}/disp.csv")
            for _, row in df.iterrows():
                self.disps[row['disp_id']] = row.to_dict()
            print(f"  ✓ Loaded {len(self.disps)} dispositions")

            # Load districts
            df = pd.read_csv(f"{PRESENT_PATH}/district.csv")
            for _, row in df.iterrows():
                district_id = str(row['A1'])
                self.districts[district_id] = row.to_dict()
            print(f"  ✓ Loaded {len(self.districts)} districts")

            # Load transactions
            df = pd.read_csv(f"{PRESENT_PATH}/trans.csv")
            for _, row in df.iterrows():
                account_id = int(row['account_id'])
                self.transactions[account_id].append(row.to_dict())
            print(f"  ✓ Loaded {sum(len(v) for v in self.transactions.values())} transactions")

            # Load loans
            df = pd.read_csv(f"{PRESENT_PATH}/loan.csv")
            for _, row in df.iterrows():
                account_id = int(row['account_id'])
                self.loans[account_id].append(row.to_dict())
            print(f"  ✓ Loaded {sum(len(v) for v in self.loans.values())} loans")

            # Load loan labels (indexed by client_id)
            if os.path.exists(f"{PRESENT_PATH}/loan_labels.csv"):
                df = pd.read_csv(f"{PRESENT_PATH}/loan_labels.csv")
                for _, row in df.iterrows():
                    client_id = int(row['client_id'])
                    self.loan_labels[client_id] = row.to_dict()
                print(f"  ✓ Loaded {len(self.loan_labels)} loan labels")

            # Load orders
            df = pd.read_csv(f"{PRESENT_PATH}/order.csv")
            for _, row in df.iterrows():
                account_id = int(row['account_id'])
                self.orders[account_id].append(row.to_dict())
            print(f"  ✓ Loaded {sum(len(v) for v in self.orders.values())} orders")

            # Load cards
            df = pd.read_csv(f"{PRESENT_PATH}/card.csv")
            for _, row in df.iterrows():
                disp_id = int(row['disp_id'])
                self.cards[disp_id].append(row.to_dict())
            print(f"  ✓ Loaded {sum(len(v) for v in self.cards.values())} cards")

            # Load card labels (indexed by client_id)
            if os.path.exists(f"{PRESENT_PATH}/card_labels.csv"):
                df = pd.read_csv(f"{PRESENT_PATH}/card_labels.csv")
                for _, row in df.iterrows():
                    client_id = int(row['client_id'])
                    self.card_labels[client_id] = row.to_dict()
                print(f"  ✓ Loaded {len(self.card_labels)} card labels")

            print(f"\n✓ Initial data loaded successfully\n")
            return True

        except Exception as e:
            print(f"\n✗ Error loading present_tables: {e}\n")
            return False

    def calculate_client_features(self, client_id):
        """Calculate ALL features for a specific client matching master CSV format"""
        if client_id not in self.clients:
            return None

        client = self.clients[client_id]

        # Initialize features with defaults
        features = {
            'client_id': client_id,
            'birth_number': client.get('birth_number', ''),
            'district_id': client.get('district_id', 0),
        }

        # Get client's accounts through dispositions
        client_accounts = []
        client_disp_ids = []
        account_frequency = None

        for disp_id, disp in self.disps.items():
            if disp['client_id'] == client_id:
                account_id = disp['account_id']
                client_disp_ids.append(disp_id)
                if account_id in self.accounts:
                    client_accounts.append(account_id)
                    if account_frequency is None:
                        account_frequency = self.accounts[account_id].get('frequency', '')

        features['num_accounts'] = len(client_accounts)
        features['frequency'] = account_frequency if account_frequency else ''

        # ===== TRANSACTION FEATURES =====
        all_trans = []
        for acc_id in client_accounts:
            all_trans.extend(self.transactions.get(acc_id, []))

        if all_trans:
            incoming = [t for t in all_trans if t.get('type') == 'PRIJEM']
            outgoing = [t for t in all_trans if t.get('type') == 'VYDAJ']

            incoming_amounts = [t['amount'] * CZK_TO_USD for t in incoming]
            outgoing_amounts = [t['amount'] * CZK_TO_USD for t in outgoing]
            all_amounts = [t['amount'] * CZK_TO_USD for t in all_trans]
            balances = [t.get('balance', 0) * CZK_TO_USD for t in all_trans if 'balance' in t]

            features['total_transactions'] = len(all_trans)
            features['num_incoming'] = len(incoming)
            features['num_outgoing'] = len(outgoing)
            features['total_incoming'] = sum(incoming_amounts)
            features['total_outgoing'] = sum(outgoing_amounts)
            features['avg_incoming'] = np.mean(incoming_amounts) if incoming_amounts else 0
            features['avg_outgoing'] = np.mean(outgoing_amounts) if outgoing_amounts else 0
            features['median_incoming'] = np.median(incoming_amounts) if incoming_amounts else 0
            features['median_outgoing'] = np.median(outgoing_amounts) if outgoing_amounts else 0
            features['std_incoming'] = np.std(incoming_amounts) if len(incoming_amounts) > 1 else 0
            features['std_outgoing'] = np.std(outgoing_amounts) if len(outgoing_amounts) > 1 else 0
            features['max_incoming'] = max(incoming_amounts) if incoming_amounts else 0
            features['max_outgoing'] = max(outgoing_amounts) if outgoing_amounts else 0
            features['min_incoming'] = min(incoming_amounts) if incoming_amounts else 0
            features['min_outgoing'] = min(outgoing_amounts) if outgoing_amounts else 0

            features['balance_min'] = min(balances) if balances else 0
            features['balance_max'] = max(balances) if balances else 0
            features['balance_mean'] = np.mean(balances) if balances else 0
            features['balance_median'] = np.median(balances) if balances else 0
            features['balance_std'] = np.std(balances) if len(balances) > 1 else 0

            features['unique_k_symbols'] = len(set(t.get('k_symbol', '') for t in all_trans if t.get('k_symbol')))
            features['unique_operations'] = len(set(t.get('operation', '') for t in all_trans if t.get('operation')))
            features['unique_banks'] = len(set(t.get('bank', '') for t in all_trans if t.get('bank')))

            # Transaction dates
            trans_dates = [int(t['date']) for t in all_trans if 'date' in t and t['date']]
            if trans_dates:
                features['first_transaction_date'] = str(min(trans_dates))
                features['last_transaction_date'] = str(max(trans_dates))
                features['transaction_span_days'] = max(trans_dates) - min(trans_dates)
            else:
                features['first_transaction_date'] = ''
                features['last_transaction_date'] = ''
                features['transaction_span_days'] = 0

            features['net_cashflow'] = features['total_incoming'] - features['total_outgoing']
            features['incoming_outgoing_ratio'] = (features['total_incoming'] / features['total_outgoing']) if features['total_outgoing'] > 0 else 0
            features['avg_transaction_amount'] = np.mean(all_amounts) if all_amounts else 0
            features['transaction_frequency'] = len(all_trans) / max(features['transaction_span_days'], 1)

            features['balance_volatility'] = features['balance_std']
            features['incoming_volatility'] = features['std_incoming']
            features['outgoing_volatility'] = features['std_outgoing']
            features['max_to_avg_incoming_ratio'] = (features['max_incoming'] / features['avg_incoming']) if features['avg_incoming'] > 0 else 0
            features['max_to_avg_outgoing_ratio'] = (features['max_outgoing'] / features['avg_outgoing']) if features['avg_outgoing'] > 0 else 0

            # IDs
            features['trans_id'] = str(all_trans[0].get('trans_id', '')) if all_trans else ''
            features['account_id'] = str(client_accounts[0]) if client_accounts else ''

        else:
            # Default transaction features
            trans_features = {
                'total_transactions': 0, 'num_incoming': 0, 'num_outgoing': 0,
                'total_incoming': 0, 'total_outgoing': 0, 'avg_incoming': 0, 'avg_outgoing': 0,
                'median_incoming': 0, 'median_outgoing': 0, 'std_incoming': 0, 'std_outgoing': 0,
                'max_incoming': 0, 'max_outgoing': 0, 'min_incoming': 0, 'min_outgoing': 0,
                'balance_min': 0, 'balance_max': 0, 'balance_mean': 0, 'balance_median': 0, 'balance_std': 0,
                'unique_k_symbols': 0, 'unique_operations': 0, 'unique_banks': 0,
                'transaction_span_days': 0, 'net_cashflow': 0, 'incoming_outgoing_ratio': 0,
                'avg_transaction_amount': 0, 'transaction_frequency': 0, 'balance_volatility': 0,
                'incoming_volatility': 0, 'outgoing_volatility': 0,
                'max_to_avg_incoming_ratio': 0, 'max_to_avg_outgoing_ratio': 0,
                'first_transaction_date': '', 'last_transaction_date': '',
                'trans_id': '', 'account_id': ''
            }
            features.update(trans_features)

        # ===== LOAN FEATURES =====
        all_loans = []
        for acc_id in client_accounts:
            all_loans.extend(self.loans.get(acc_id, []))

        if all_loans:
            loan_amounts = [l['amount'] * CZK_TO_USD for l in all_loans]
            loan_durations = [l['duration'] for l in all_loans]
            loan_payments = [l['payments'] * CZK_TO_USD for l in all_loans]
            loan_dates = [int(l['date']) for l in all_loans if 'date' in l]

            features['num_loans'] = len(all_loans)
            features['loan_amount_total_usd'] = sum(loan_amounts)
            features['loan_amount_avg_usd'] = np.mean(loan_amounts)
            features['loan_amount_max_usd'] = max(loan_amounts)
            features['loan_amount_min_usd'] = min(loan_amounts)
            features['loan_duration_avg'] = np.mean(loan_durations)
            features['loan_duration_max'] = max(loan_durations)
            features['loan_duration_min'] = min(loan_durations)
            features['loan_payment_avg_usd'] = np.mean(loan_payments)
            features['loan_payment_max_usd'] = max(loan_payments)
            features['loan_payment_min_usd'] = min(loan_payments)

            features['loan_status_all'] = ','.join(set(l.get('status', '') for l in all_loans))
            features['loan_id'] = str(all_loans[0].get('loan_id', ''))

            if loan_dates:
                features['first_loan_date'] = str(min(loan_dates))
                features['last_loan_date'] = str(max(loan_dates))
            else:
                features['first_loan_date'] = ''
                features['last_loan_date'] = ''

            # Loan purpose flags (from loan_labels indexed by client_id)
            if client_id in self.loan_labels:
                labels = self.loan_labels[client_id]
                features['car_loan'] = int(labels.get('car_loan', 0))
                features['personal_loan'] = int(labels.get('personal_loan', 0))
                features['home_loan'] = int(labels.get('home_loan', 0))
                features['business_loan'] = int(labels.get('business_loan', 0))
            else:
                features['car_loan'] = 0
                features['personal_loan'] = 0
                features['home_loan'] = 0
                features['business_loan'] = 0

        else:
            loan_features = {
                'num_loans': 0, 'loan_amount_total_usd': 0, 'loan_amount_avg_usd': 0,
                'loan_amount_max_usd': 0, 'loan_amount_min_usd': 0, 'loan_duration_avg': 0,
                'loan_duration_max': 0, 'loan_duration_min': 0, 'loan_payment_avg_usd': 0,
                'loan_payment_max_usd': 0, 'loan_payment_min_usd': 0, 'loan_status_all': '',
                'first_loan_date': '', 'last_loan_date': '', 'loan_id': '',
                'car_loan': 0, 'personal_loan': 0, 'home_loan': 0, 'business_loan': 0
            }
            features.update(loan_features)

        # ===== ORDER FEATURES =====
        all_orders = []
        for acc_id in client_accounts:
            all_orders.extend(self.orders.get(acc_id, []))

        if all_orders:
            order_amounts = [o['amount'] * CZK_TO_USD for o in all_orders]

            features['num_orders'] = len(all_orders)
            features['avg_order_amount_usd'] = np.mean(order_amounts)
            features['total_order_amount_usd'] = sum(order_amounts)
            features['max_order_amount_usd'] = max(order_amounts)
            features['min_order_amount_usd'] = min(order_amounts)
            features['std_order_amount_usd'] = np.std(order_amounts) if len(order_amounts) > 1 else 0
            features['unique_banks_orders'] = len(set(o.get('bank_to', '') for o in all_orders if o.get('bank_to')))
            features['unique_k_symbols_orders'] = len(set(o.get('k_symbol', '') for o in all_orders if o.get('k_symbol')))
            features['order_id'] = str(all_orders[0].get('order_id', ''))
        else:
            order_features = {
                'num_orders': 0, 'avg_order_amount_usd': 0, 'total_order_amount_usd': 0,
                'max_order_amount_usd': 0, 'min_order_amount_usd': 0, 'std_order_amount_usd': 0,
                'unique_banks_orders': 0, 'unique_k_symbols_orders': 0, 'order_id': ''
            }
            features.update(order_features)

        # ===== CARD FEATURES =====
        client_cards = []
        for disp_id in client_disp_ids:
            client_cards.extend(self.cards.get(disp_id, []))

        features['num_cards'] = len(client_cards)
        features['num_classic_cards'] = sum(1 for c in client_cards if c.get('type', '').lower() == 'classic')
        features['num_junior_cards'] = sum(1 for c in client_cards if c.get('type', '').lower() == 'junior')
        features['num_gold_cards'] = sum(1 for c in client_cards if c.get('type', '').lower() == 'gold')

        # Card type flags
        features['gold_card'] = 1 if features['num_gold_cards'] > 0 else 0
        features['classic_card'] = 1 if features['num_classic_cards'] > 0 else 0
        features['junior_card'] = 1 if features['num_junior_cards'] > 0 else 0

        if client_cards:
            card_issued = [c.get('issued', '') for c in client_cards if c.get('issued')]
            features['earliest_card_issue'] = min(card_issued) if card_issued else ''
            features['latest_card_issue'] = max(card_issued) if card_issued else ''
            features['card_id'] = str(client_cards[0].get('card_id', ''))
        else:
            features['earliest_card_issue'] = ''
            features['latest_card_issue'] = ''
            features['card_id'] = ''

        # ===== DISTRICT FEATURES =====
        district_id = str(client.get('district_id', ''))
        if district_id in self.districts:
            district = self.districts[district_id]
            for i in range(1, 17):
                key = f'A{i}'
                val = district.get(key, 0)
                # Handle '?' values
                if val == '?':
                    val = 0
                features[key] = val
        else:
            for i in range(1, 17):
                features[f'A{i}'] = 0

        # ===== LOAN PURPOSE (if not already set) =====
        if 'loan_purpose' not in features:
            if features.get('car_loan'):
                features['loan_purpose'] = 'car'
            elif features.get('home_loan'):
                features['loan_purpose'] = 'home'
            elif features.get('business_loan'):
                features['loan_purpose'] = 'business'
            elif features.get('personal_loan'):
                features['loan_purpose'] = 'personal'
            else:
                features['loan_purpose'] = ''

        return features

    async def publish_features(self, features):
        """Publish features to NATS"""
        if features and self.nc:
            subject = SUBJECTS['client_features']
            message = json.dumps(features, default=str)
            await self.nc.publish(subject, message.encode())

    async def calculate_and_publish_all_features(self):
        """Calculate features for all clients and publish"""
        self.feature_calc_count += 1
        calc_time = datetime.now()

        print(f"\n[CALC #{self.feature_calc_count}] Calculating features for {len(self.clients)} clients...")

        published = 0
        # Create a snapshot of client IDs to avoid RuntimeError during iteration
        client_ids = list(self.clients.keys())
        for client_id in client_ids:
            features = self.calculate_client_features(client_id)
            if features:
                await self.publish_features(features)
                published += 1

        elapsed = (datetime.now() - calc_time).total_seconds()
        print(f"  ✓ Published {published} feature sets in {elapsed:.2f}s")
        print(f"  ✓ Total messages processed: {self.message_count}\n")

        self.last_calc_time = datetime.now()

    async def handle_table_update(self, table_name, data):
        """Handle incoming table update from NATS"""
        self.message_count += 1

        try:
            if table_name == 'client':
                self.clients[data['client_id']] = data
            elif table_name == 'account':
                self.accounts[data['account_id']] = data
            elif table_name == 'disp':
                self.disps[data['disp_id']] = data
            elif table_name == 'trans':
                self.transactions[int(data['account_id'])].append(data)
            elif table_name == 'loan':
                self.loans[int(data['account_id'])].append(data)
            elif table_name == 'loan_labels':
                self.loan_labels[int(data['client_id'])] = data
            elif table_name == 'order':
                self.orders[int(data['account_id'])].append(data)
            elif table_name == 'card':
                self.cards[int(data['disp_id'])].append(data)
            elif table_name == 'card_labels':
                self.card_labels[int(data['client_id'])] = data
            elif table_name == 'district':
                self.districts[str(data['A1'])] = data

            if self.message_count % 10 == 0:
                print(f"[MSG #{self.message_count:4d}] Updated {table_name}")

            if self.message_count % self.calc_every_n_messages == 0:
                await self.calculate_and_publish_all_features()

        except Exception as e:
            print(f"[ERROR] Failed to process {table_name} update: {e}")

    async def subscribe_to_tables(self):
        """Subscribe to all table topics on NATS"""
        print("Subscribing to NATS topics...\n")

        tables = ['client', 'account', 'disp', 'trans', 'loan', 'loan_labels',
                  'order', 'card', 'card_labels', 'district']

        for table in tables:
            subject = SUBJECTS.get(table)
            if not subject:
                continue

            async def handler(msg, t=table):
                data = json.loads(msg.data.decode())
                await self.handle_table_update(t, data)

            await self.nc.subscribe(subject, cb=handler)
            print(f"  ✓ Subscribed to {subject}")

        print(f"\n✓ Subscribed to {len(tables)} table topics\n")

    async def connect(self):
        """Connect to NATS"""
        self.nc = NATS()
        try:
            await self.nc.connect(NATS_SERVER)
            print(f"✓ Connected to NATS at {NATS_SERVER}\n")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to NATS: {e}")
            print("\nPlease start NATS server first:")
            print("  docker start nats-server\n")
            return False

    async def disconnect(self):
        """Disconnect from NATS"""
        if self.nc:
            await self.nc.close()
            print("\n✓ Disconnected from NATS")

    async def run(self):
        """Main execution loop"""
        print("="*80)
        print("DATA FETCH - COMPLETE FEATURE CALCULATION")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"NATS Server: {NATS_SERVER}")
        print("="*80)

        if not self.load_present_tables():
            return

        if not await self.connect():
            return

        await self.subscribe_to_tables()

        print("Calculating initial features...\n")
        await self.calculate_and_publish_all_features()

        print("="*80)
        print("LISTENING FOR STREAMING UPDATES")
        print("="*80)
        print(f"Will calculate features every {self.calc_every_n_messages} messages")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n✓ Interrupted by user")
        finally:
            await self.disconnect()


async def main():
    processor = DataProcessor()
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
