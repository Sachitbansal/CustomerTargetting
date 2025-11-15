"""
Data Fetch - NATS-Based Real-Time Feature Calculation

This script:
1. Loads initial data from present_tables (CSV)
2. Subscribes to NATS for streaming updates
3. Maintains in-memory data stores
4. Calculates client features every N messages
5. Publishes features to NATS (banking.features.client)
"""

import asyncio
import pandas as pd
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
        self.clients = {}  # client_id -> client_data
        self.accounts = {}  # account_id -> account_data
        self.disps = {}  # disp_id -> disp_data
        self.districts = {}  # district_id -> district_data
        self.transactions = defaultdict(list)  # account_id -> [transactions]
        self.loans = defaultdict(list)  # account_id -> [loans]
        self.orders = defaultdict(list)  # account_id -> [orders]
        self.cards = defaultdict(list)  # disp_id -> [cards]

        # Statistics
        self.message_count = 0
        self.feature_calc_count = 0
        self.last_calc_time = datetime.now()

        # Configuration
        self.calc_every_n_messages = 50  # Calculate features every N messages

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
                district_id = str(row['A1'])  # District ID is in A1 column
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

            print(f"\n✓ Initial data loaded successfully\n")
            return True

        except Exception as e:
            print(f"\n✗ Error loading present_tables: {e}\n")
            return False

    def calculate_client_features(self, client_id):
        """Calculate features for a specific client"""
        if client_id not in self.clients:
            return None

        client = self.clients[client_id]
        features = {
            'client_id': client_id,
            'birth_number': client.get('birth_number', ''),
            'district_id': client.get('district_id', 0)
        }

        # Get client's accounts through dispositions
        client_accounts = []
        for disp_id, disp in self.disps.items():
            if disp['client_id'] == client_id:
                account_id = disp['account_id']
                if account_id in self.accounts:
                    client_accounts.append(account_id)

        # Transaction features
        all_trans = []
        for acc_id in client_accounts:
            all_trans.extend(self.transactions.get(acc_id, []))

        if all_trans:
            incoming = [t for t in all_trans if t['type'] == 'PRIJEM']
            outgoing = [t for t in all_trans if t['type'] == 'VYDAJ']

            features['num_transactions'] = len(all_trans)
            features['total_incoming'] = sum(t['amount'] for t in incoming) * CZK_TO_USD
            features['total_outgoing'] = sum(t['amount'] for t in outgoing) * CZK_TO_USD
            features['avg_incoming'] = (features['total_incoming'] / len(incoming)) if incoming else 0
            features['avg_outgoing'] = (features['total_outgoing'] / len(outgoing)) if outgoing else 0
            features['net_cashflow'] = features['total_incoming'] - features['total_outgoing']
        else:
            features.update({
                'num_transactions': 0, 'total_incoming': 0, 'total_outgoing': 0,
                'avg_incoming': 0, 'avg_outgoing': 0, 'net_cashflow': 0
            })

        # Loan features
        all_loans = []
        for acc_id in client_accounts:
            all_loans.extend(self.loans.get(acc_id, []))

        if all_loans:
            features['num_loans'] = len(all_loans)
            features['total_loan_amount'] = sum(l['amount'] for l in all_loans) * CZK_TO_USD
            features['avg_loan_amount'] = features['total_loan_amount'] / len(all_loans)
            features['avg_loan_duration'] = sum(l['duration'] for l in all_loans) / len(all_loans)
        else:
            features.update({
                'num_loans': 0, 'total_loan_amount': 0,
                'avg_loan_amount': 0, 'avg_loan_duration': 0
            })

        # Order features
        all_orders = []
        for acc_id in client_accounts:
            all_orders.extend(self.orders.get(acc_id, []))

        if all_orders:
            features['num_orders'] = len(all_orders)
            features['total_order_amount'] = sum(o['amount'] for o in all_orders) * CZK_TO_USD
            features['avg_order_amount'] = features['total_order_amount'] / len(all_orders)
        else:
            features.update({
                'num_orders': 0, 'total_order_amount': 0, 'avg_order_amount': 0
            })

        # Card features
        client_cards = []
        for disp_id, disp in self.disps.items():
            if disp['client_id'] == client_id:
                client_cards.extend(self.cards.get(disp_id, []))

        features['num_cards'] = len(client_cards)

        # District features
        district_id = str(client.get('district_id', ''))
        if district_id in self.districts:
            district = self.districts[district_id]
            for i in range(1, 17):
                key = f'A{i}'
                features[key] = district.get(key, 0)
        else:
            for i in range(1, 17):
                features[f'A{i}'] = 0

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
        for client_id in self.clients.keys():
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
                client_id = data['client_id']
                self.clients[client_id] = data

            elif table_name == 'account':
                account_id = data['account_id']
                self.accounts[account_id] = data

            elif table_name == 'disp':
                disp_id = data['disp_id']
                self.disps[disp_id] = data

            elif table_name == 'trans':
                account_id = int(data['account_id'])
                self.transactions[account_id].append(data)

            elif table_name == 'loan':
                account_id = int(data['account_id'])
                self.loans[account_id].append(data)

            elif table_name == 'order':
                account_id = int(data['account_id'])
                self.orders[account_id].append(data)

            elif table_name == 'card':
                disp_id = int(data['disp_id'])
                self.cards[disp_id].append(data)

            elif table_name == 'district':
                district_id = str(data['A1'])
                self.districts[district_id] = data

            # Print progress
            if self.message_count % 10 == 0:
                print(f"[MSG #{self.message_count:4d}] Updated {table_name}")

            # Calculate and publish features every N messages
            if self.message_count % self.calc_every_n_messages == 0:
                await self.calculate_and_publish_all_features()

        except Exception as e:
            print(f"[ERROR] Failed to process {table_name} update: {e}")

    async def subscribe_to_tables(self):
        """Subscribe to all table topics on NATS"""
        print("Subscribing to NATS topics...\n")

        tables = ['client', 'account', 'disp', 'trans', 'loan', 'order', 'card', 'district']

        for table in tables:
            subject = SUBJECTS[table]

            # Create handler for this table
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
        print("DATA FETCH - NATS REAL-TIME FEATURE CALCULATION")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"NATS Server: {NATS_SERVER}")
        print("="*80)

        # Load initial data
        if not self.load_present_tables():
            return

        # Connect to NATS
        if not await self.connect():
            return

        # Subscribe to table topics
        await self.subscribe_to_tables()

        # Calculate initial features
        print("Calculating initial features...\n")
        await self.calculate_and_publish_all_features()

        print("="*80)
        print("LISTENING FOR STREAMING UPDATES")
        print("="*80)
        print(f"Will calculate features every {self.calc_every_n_messages} messages")
        print("Press Ctrl+C to stop\n")

        # Keep running
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
