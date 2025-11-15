"""
Data Fetch - Subscribe to NATS and calculate ALL client features in real-time
"""

import asyncio
import pandas as pd
import numpy as np
import json
from nats.aio.client import Client as NATS
from nats_config import NATS_SERVER, SUBJECTS, CZK_TO_USD
from datetime import datetime
from collections import defaultdict


class FeatureCalculator:
    def __init__(self):
        self.nc = None

        # In-memory data storage
        self.client_data = {}
        self.account_data = {}
        self.disp_data = {}
        self.trans_data = defaultdict(list)
        self.loan_data = defaultdict(list)
        self.order_data = defaultdict(list)
        self.card_data = defaultdict(list)
        self.district_data = {}
        self.loan_labels_data = {}
        self.card_labels_data = {}

        # Counters
        self.message_counts = defaultdict(int)
        self.total_messages = 0
        self.last_calculation_time = datetime.now()
        self.features_published = 0

    async def connect(self):
        """Connect to NATS server"""
        self.nc = NATS()
        try:
            await self.nc.connect(NATS_SERVER)
            print(f"✓ Connected to NATS at {NATS_SERVER}\n")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to NATS: {e}")
            return False

    async def disconnect(self):
        """Disconnect from NATS"""
        if self.nc:
            await self.nc.close()
            print("\n✓ Disconnected from NATS")

    def calculate_features(self):
        """Calculate all client features from current data"""
        if not self.client_data:
            return []

        client_df = pd.DataFrame.from_dict(self.client_data, orient='index')
        features_list = []

        for client_id in client_df.index:
            try:
                features = self._calculate_client_features(client_id)
                if features:
                    features_list.append(features)
            except Exception as e:
                print(f"  Error calculating features for client {client_id}: {e}")

        return features_list

    def _calculate_client_features(self, client_id):
        """Calculate ALL features for a single client"""
        features = {'client_id': str(client_id)}

        # Basic client info
        client_info = self.client_data.get(client_id, {})
        features['birth_number'] = str(client_info.get('birth_number', ''))
        features['district_id'] = int(client_info.get('district_id', 0))

        # Get accounts for this client via disp table
        client_accounts = []
        for disp_id, disp in self.disp_data.items():
            if str(disp.get('client_id')) == str(client_id):
                client_accounts.append(str(disp.get('account_id')))

        client_accounts = list(set(client_accounts))  # Remove duplicates
        features['num_accounts'] = len(client_accounts)

        if not client_accounts:
            return self._fill_default_features(features)

        # Account info
        account_info = [self.account_data.get(acc_id, {}) for acc_id in client_accounts]
        features['frequency'] = account_info[0].get('frequency', '') if account_info else ''
        features['account_id'] = client_accounts[0] if client_accounts else ''

        # Calculate all features
        trans_features = self._calculate_transaction_features(client_accounts)
        features.update(trans_features)

        loan_features = self._calculate_loan_features(client_accounts)
        features.update(loan_features)

        order_features = self._calculate_order_features(client_accounts)
        features.update(order_features)

        card_features = self._calculate_card_features(client_id)
        features.update(card_features)

        district_features = self._get_district_features(features['district_id'])
        features.update(district_features)

        # Loan purpose one-hot encoding
        loan_purposes = self._get_loan_purposes(client_accounts)
        features.update(loan_purposes)

        # Card type one-hot encoding
        card_types = self._get_card_type_one_hot(client_id)
        features.update(card_types)

        return features

    def _calculate_transaction_features(self, account_ids):
        """Calculate ALL transaction features"""
        all_trans = []
        for acc_id in account_ids:
            all_trans.extend(self.trans_data.get(acc_id, []))

        if not all_trans:
            return self._default_transaction_features()

        trans_df = pd.DataFrame(all_trans)

        # Convert to USD
        trans_df['amount_usd'] = trans_df['amount'].astype(float) * CZK_TO_USD
        trans_df['balance_usd'] = trans_df['balance'].astype(float) * CZK_TO_USD

        # Parse dates
        if 'date' in trans_df.columns:
            trans_df['date'] = pd.to_datetime(trans_df['date'], errors='coerce')

        # Separate incoming/outgoing
        incoming = trans_df[trans_df['type'] == 'PRIJEM']
        outgoing = trans_df[trans_df['type'] == 'VYDAJ']

        # Basic counts
        total_incoming = incoming['amount_usd'].sum() if len(incoming) > 0 else 0
        total_outgoing = outgoing['amount_usd'].sum() if len(outgoing) > 0 else 0
        avg_incoming = incoming['amount_usd'].mean() if len(incoming) > 0 else 0
        avg_outgoing = outgoing['amount_usd'].mean() if len(outgoing) > 0 else 0

        features = {
            'total_transactions': len(trans_df),
            'num_incoming': len(incoming),
            'num_outgoing': len(outgoing),
            'total_incoming': total_incoming,
            'total_outgoing': total_outgoing,
            'avg_incoming': avg_incoming,
            'avg_outgoing': avg_outgoing,
            'median_incoming': incoming['amount_usd'].median() if len(incoming) > 0 else 0,
            'median_outgoing': outgoing['amount_usd'].median() if len(outgoing) > 0 else 0,
            'std_incoming': incoming['amount_usd'].std() if len(incoming) > 0 else 0,
            'std_outgoing': outgoing['amount_usd'].std() if len(outgoing) > 0 else 0,
            'min_incoming': incoming['amount_usd'].min() if len(incoming) > 0 else 0,
            'min_outgoing': outgoing['amount_usd'].min() if len(outgoing) > 0 else 0,
            'max_incoming': incoming['amount_usd'].max() if len(incoming) > 0 else 0,
            'max_outgoing': outgoing['amount_usd'].max() if len(outgoing) > 0 else 0,
            'balance_min': trans_df['balance_usd'].min(),
            'balance_max': trans_df['balance_usd'].max(),
            'balance_mean': trans_df['balance_usd'].mean(),
            'balance_median': trans_df['balance_usd'].median(),
            'balance_std': trans_df['balance_usd'].std(),
            'unique_k_symbols': trans_df['k_symbol'].nunique() if 'k_symbol' in trans_df.columns else 0,
            'unique_operations': trans_df['operation'].nunique() if 'operation' in trans_df.columns else 0,
            'unique_banks': trans_df['bank'].nunique() if 'bank' in trans_df.columns else 0,
        }

        # Calculated metrics
        features['net_cashflow'] = total_incoming - total_outgoing
        features['incoming_outgoing_ratio'] = (total_incoming / total_outgoing) if total_outgoing > 0 else 0
        features['avg_transaction_amount'] = trans_df['amount_usd'].abs().mean()

        # Transaction span in days
        if 'date' in trans_df.columns and trans_df['date'].notna().any():
            date_range = (trans_df['date'].max() - trans_df['date'].min()).days
            features['transaction_span_days'] = date_range
            features['transaction_frequency'] = len(trans_df) / max(date_range, 1) * 30  # per month
            features['first_transaction_date'] = trans_df['date'].min().strftime('%Y-%m-%d') if pd.notna(trans_df['date'].min()) else ''
            features['last_transaction_date'] = trans_df['date'].max().strftime('%Y-%m-%d') if pd.notna(trans_df['date'].max()) else ''
        else:
            features['transaction_span_days'] = 0
            features['transaction_frequency'] = 0
            features['first_transaction_date'] = ''
            features['last_transaction_date'] = ''

        # Volatility metrics
        features['balance_volatility'] = trans_df['balance_usd'].std() / trans_df['balance_usd'].mean() if trans_df['balance_usd'].mean() > 0 else 0
        features['incoming_volatility'] = features['std_incoming'] / avg_incoming if avg_incoming > 0 else 0
        features['outgoing_volatility'] = features['std_outgoing'] / avg_outgoing if avg_outgoing > 0 else 0

        # Ratio metrics
        features['max_to_avg_incoming_ratio'] = features['max_incoming'] / avg_incoming if avg_incoming > 0 else 0
        features['max_to_avg_outgoing_ratio'] = features['max_outgoing'] / avg_outgoing if avg_outgoing > 0 else 0

        # Get last trans_id
        features['trans_id'] = trans_df.iloc[-1]['trans_id'] if 'trans_id' in trans_df.columns and len(trans_df) > 0 else ''

        return features

    def _calculate_loan_features(self, account_ids):
        """Calculate ALL loan features"""
        all_loans = []
        for acc_id in account_ids:
            all_loans.extend(self.loan_data.get(acc_id, []))

        if not all_loans:
            return self._default_loan_features()

        loan_df = pd.DataFrame(all_loans)

        # Convert to USD
        loan_df['amount_usd'] = loan_df['amount'].astype(float) * CZK_TO_USD
        loan_df['payments_usd'] = loan_df['payments'].astype(float) * CZK_TO_USD

        features = {
            'num_loans': len(loan_df),
            'loan_amount_total_usd': loan_df['amount_usd'].sum(),
            'loan_amount_avg_usd': loan_df['amount_usd'].mean(),
            'loan_amount_min_usd': loan_df['amount_usd'].min(),
            'loan_amount_max_usd': loan_df['amount_usd'].max(),
            'loan_duration_avg': loan_df['duration'].astype(float).mean(),
            'loan_duration_min': loan_df['duration'].astype(float).min(),
            'loan_duration_max': loan_df['duration'].astype(float).max(),
            'loan_payment_avg_usd': loan_df['payments_usd'].mean(),
            'loan_payment_min_usd': loan_df['payments_usd'].min(),
            'loan_payment_max_usd': loan_df['payments_usd'].max(),
            'loan_status_all': ','.join(loan_df['status'].unique().astype(str)) if 'status' in loan_df.columns else '',
        }

        # Dates
        if 'date' in loan_df.columns:
            loan_df['date'] = pd.to_datetime(loan_df['date'], errors='coerce')
            features['first_loan_date'] = loan_df['date'].min().strftime('%Y-%m-%d') if pd.notna(loan_df['date'].min()) else ''
            features['last_loan_date'] = loan_df['date'].max().strftime('%Y-%m-%d') if pd.notna(loan_df['date'].max()) else ''
        else:
            features['first_loan_date'] = ''
            features['last_loan_date'] = ''

        # Get last loan_id
        features['loan_id'] = loan_df.iloc[-1]['loan_id'] if 'loan_id' in loan_df.columns and len(loan_df) > 0 else ''

        return features

    def _calculate_order_features(self, account_ids):
        """Calculate ALL order features"""
        all_orders = []
        for acc_id in account_ids:
            all_orders.extend(self.order_data.get(acc_id, []))

        if not all_orders:
            return self._default_order_features()

        order_df = pd.DataFrame(all_orders)
        order_df['amount_usd'] = order_df['amount'].astype(float) * CZK_TO_USD

        features = {
            'num_orders': len(order_df),
            'total_order_amount_usd': order_df['amount_usd'].sum(),
            'avg_order_amount_usd': order_df['amount_usd'].mean(),
            'min_order_amount_usd': order_df['amount_usd'].min(),
            'max_order_amount_usd': order_df['amount_usd'].max(),
            'std_order_amount_usd': order_df['amount_usd'].std(),
            'unique_banks_orders': order_df['bank_to'].nunique() if 'bank_to' in order_df.columns else 0,
            'unique_k_symbols_orders': order_df['k_symbol'].nunique() if 'k_symbol' in order_df.columns else 0,
        }

        # Get last order_id
        features['order_id'] = order_df.iloc[-1]['order_id'] if 'order_id' in order_df.columns and len(order_df) > 0 else ''

        return features

    def _calculate_card_features(self, client_id):
        """Calculate ALL card features"""
        # Get cards via disp table
        client_disp_ids = [disp_id for disp_id, disp in self.disp_data.items()
                          if str(disp.get('client_id')) == str(client_id)]

        client_cards = []
        for card_id, card in self.card_data.items():
            if str(card.get('disp_id')) in [str(d) for d in client_disp_ids]:
                client_cards.append(card)

        if not client_cards:
            return self._default_card_features()

        card_df = pd.DataFrame(client_cards)

        # Count by type
        type_counts = card_df['type'].value_counts() if 'type' in card_df.columns else pd.Series()

        features = {
            'num_cards': len(card_df),
            'num_classic_cards': int(type_counts.get('classic', 0)),
            'num_junior_cards': int(type_counts.get('junior', 0)),
            'num_gold_cards': int(type_counts.get('gold', 0)),
        }

        # Dates
        if 'issued' in card_df.columns:
            card_df['issued'] = pd.to_datetime(card_df['issued'], errors='coerce')
            features['earliest_card_issue'] = card_df['issued'].min().strftime('%Y-%m-%d') if pd.notna(card_df['issued'].min()) else ''
            features['latest_card_issue'] = card_df['issued'].max().strftime('%Y-%m-%d') if pd.notna(card_df['issued'].max()) else ''
        else:
            features['earliest_card_issue'] = ''
            features['latest_card_issue'] = ''

        # Get last card_id
        features['card_id'] = card_df.iloc[-1]['card_id'] if 'card_id' in card_df.columns and len(card_df) > 0 else ''

        return features

    def _get_district_features(self, district_id):
        """Get district demographic features A1-A16"""
        district = self.district_data.get(str(district_id), {})

        features = {}
        for i in range(1, 17):
            col_name = f'A{i}'
            value = district.get(col_name, 0)
            # Handle non-numeric values
            try:
                features[col_name] = float(value) if value not in ['?', '', None] else 0
            except:
                features[col_name] = 0

        return features

    def _get_loan_purposes(self, account_ids):
        """Get one-hot encoded loan purposes"""
        all_loan_ids = []
        for acc_id in account_ids:
            loans = self.loan_data.get(acc_id, [])
            all_loan_ids.extend([loan.get('loan_id') for loan in loans if loan.get('loan_id')])

        purposes = set()
        for loan_id in all_loan_ids:
            label = self.loan_labels_data.get(str(loan_id), {})
            purpose = label.get('purpose', '')
            if purpose:
                purposes.add(purpose)

        # One-hot encode common purposes
        loan_purposes = ['car_loan', 'personal_loan', 'business_loan', 'home_loan']
        features = {}

        for purpose in loan_purposes:
            # Check if any purpose matches (case insensitive)
            has_purpose = any(purpose.replace('_', '').lower() in p.lower().replace(' ', '') for p in purposes)
            features[purpose] = 1 if has_purpose else 0

        return features

    def _get_card_type_one_hot(self, client_id):
        """Get one-hot encoded card types"""
        # Get cards for this client
        client_disp_ids = [disp_id for disp_id, disp in self.disp_data.items()
                          if str(disp.get('client_id')) == str(client_id)]

        card_types = set()
        for card_id, card in self.card_data.items():
            if str(card.get('disp_id')) in [str(d) for d in client_disp_ids]:
                card_type = card.get('type', '')
                if card_type:
                    card_types.add(card_type.lower())

        features = {
            'gold_card': 1 if 'gold' in card_types else 0,
            'classic_card': 1 if 'classic' in card_types else 0,
            'junior_card': 1 if 'junior' in card_types else 0,
        }

        return features

    def _default_transaction_features(self):
        """Default transaction features"""
        return {
            'total_transactions': 0, 'num_incoming': 0, 'num_outgoing': 0,
            'total_incoming': 0, 'total_outgoing': 0, 'avg_incoming': 0, 'avg_outgoing': 0,
            'median_incoming': 0, 'median_outgoing': 0, 'std_incoming': 0, 'std_outgoing': 0,
            'min_incoming': 0, 'min_outgoing': 0, 'max_incoming': 0, 'max_outgoing': 0,
            'balance_min': 0, 'balance_max': 0, 'balance_mean': 0, 'balance_median': 0, 'balance_std': 0,
            'unique_k_symbols': 0, 'unique_operations': 0, 'unique_banks': 0,
            'transaction_span_days': 0, 'net_cashflow': 0, 'incoming_outgoing_ratio': 0,
            'avg_transaction_amount': 0, 'transaction_frequency': 0, 'balance_volatility': 0,
            'incoming_volatility': 0, 'outgoing_volatility': 0, 'max_to_avg_incoming_ratio': 0,
            'max_to_avg_outgoing_ratio': 0, 'first_transaction_date': '', 'last_transaction_date': '',
            'trans_id': ''
        }

    def _default_loan_features(self):
        """Default loan features"""
        return {
            'num_loans': 0, 'loan_amount_total_usd': 0, 'loan_amount_avg_usd': 0,
            'loan_amount_max_usd': 0, 'loan_amount_min_usd': 0, 'loan_duration_avg': 0,
            'loan_duration_max': 0, 'loan_duration_min': 0, 'loan_payment_avg_usd': 0,
            'loan_payment_max_usd': 0, 'loan_payment_min_usd': 0, 'loan_status_all': '',
            'first_loan_date': '', 'last_loan_date': '', 'loan_id': ''
        }

    def _default_order_features(self):
        """Default order features"""
        return {
            'num_orders': 0, 'total_order_amount_usd': 0, 'avg_order_amount_usd': 0,
            'min_order_amount_usd': 0, 'max_order_amount_usd': 0, 'std_order_amount_usd': 0,
            'unique_banks_orders': 0, 'unique_k_symbols_orders': 0, 'order_id': ''
        }

    def _default_card_features(self):
        """Default card features"""
        return {
            'num_cards': 0, 'num_classic_cards': 0, 'num_junior_cards': 0, 'num_gold_cards': 0,
            'earliest_card_issue': '', 'latest_card_issue': '', 'card_id': ''
        }

    def _fill_default_features(self, features):
        """Fill all features with defaults"""
        features.update(self._default_transaction_features())
        features.update(self._default_loan_features())
        features.update(self._default_order_features())
        features.update(self._default_card_features())
        features.update(self._get_district_features(features.get('district_id', 0)))
        features.update({'car_loan': 0, 'personal_loan': 0, 'business_loan': 0, 'home_loan': 0})
        features.update({'gold_card': 0, 'classic_card': 0, 'junior_card': 0})
        features['num_accounts'] = 0
        features['frequency'] = ''
        features['account_id'] = ''
        return features

    async def publish_features(self, features_list):
        """Publish calculated features to NATS"""
        if not features_list:
            return

        subject = SUBJECTS['client_features']

        for features in features_list:
            message = json.dumps(features, default=str)
            await self.nc.publish(subject, message.encode())
            self.features_published += 1

        print(f"  ✓ Published {len(features_list)} client features to {subject}")
        print(f"  Total features published: {self.features_published}\n")

    async def subscribe_to_table(self, table_name):
        """Subscribe to a table's NATS subject"""
        subject = SUBJECTS.get(table_name)
        if not subject:
            return

        async def handler(msg):
            data = json.loads(msg.data.decode())
            self.message_counts[table_name] += 1
            self.total_messages += 1

            # Store data based on table type
            if table_name == 'client':
                self.client_data[data.get('client_id')] = data
            elif table_name == 'account':
                self.account_data[data.get('account_id')] = data
            elif table_name == 'disp':
                self.disp_data[data.get('disp_id')] = data
            elif table_name == 'trans':
                self.trans_data[data.get('account_id')].append(data)
            elif table_name == 'loan':
                self.loan_data[data.get('account_id')].append(data)
            elif table_name == 'order':
                self.order_data[data.get('account_id')].append(data)
            elif table_name == 'card':
                self.card_data[data.get('card_id')] = data
            elif table_name == 'district':
                self.district_data[data.get('A1')] = data
            elif table_name == 'loan_labels':
                self.loan_labels_data[data.get('loan_id')] = data
            elif table_name == 'card_labels':
                self.card_labels_data[data.get('card_id')] = data

            # Calculate and publish features every 100 messages or every 10 seconds
            time_since_calc = (datetime.now() - self.last_calculation_time).total_seconds()

            if self.total_messages % 100 == 0 or time_since_calc >= 10:
                print(f"\n[CALCULATING FEATURES] Total messages: {self.total_messages}")
                for tbl, count in sorted(self.message_counts.items()):
                    print(f"  {tbl}: {count}")

                features_list = self.calculate_features()
                await self.publish_features(features_list)
                self.last_calculation_time = datetime.now()

        await self.nc.subscribe(subject, cb=handler)
        print(f"✓ Subscribed to {subject}")

    async def run(self):
        """Main run loop"""
        print("="*80)
        print("DATA FETCH - REAL-TIME FEATURE CALCULATION FROM NATS")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"NATS Server: {NATS_SERVER}")
        print("="*80 + "\n")

        if not await self.connect():
            return

        print("Subscribing to NATS subjects...")
        for table_name in ['client', 'account', 'disp', 'trans', 'loan',
                          'order', 'card', 'district', 'loan_labels', 'card_labels']:
            await self.subscribe_to_table(table_name)

        print("\n✓ All subscriptions active\n")
        print("Listening for messages and calculating features...\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n✓ Interrupted by user")
            print("\nCalculating final features...")
            features_list = self.calculate_features()
            await self.publish_features(features_list)
        finally:
            await self.disconnect()


async def main():
    calculator = FeatureCalculator()
    await calculator.run()


if __name__ == "__main__":
    asyncio.run(main())
