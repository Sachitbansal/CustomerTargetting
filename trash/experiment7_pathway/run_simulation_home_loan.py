# run_simulation_home_loan.py

import pathway as pw
import pandas as pd
import numpy as np
import os
import argparse
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Ellipse
from sklearn.preprocessing import StandardScaler, OrdinalEncoder, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.metrics import classification_report, confusion_matrix
from datetime import datetime

# Custom imports
from streaming_hybrid_advanced import StreamingHybridAdvanced
from pipeline_config import HOME_LOAN_CONFIG # <-- Import the specific config

# --- Configuration from Imported Dictionary ---
CONFIG = HOME_LOAN_CONFIG
TARGET_COLUMN = CONFIG["target"]
GMM_NUM_FEATURES = CONFIG["gmm_num_features"]
GMM_CAT_FEATURES = CONFIG["gmm_cat_features"]
NN_NUMERICAL_FEATURES = CONFIG["nn_numerical_features"]
NN_CATEGORICAL_FEATURES = CONFIG["nn_categorical_features"]
GIF_TITLE_PREFIX = CONFIG["gif_title_prefix"]
GIF_FILENAME = CONFIG["gif_filename"]

# --- Helper Functions (moved from pipeline.py) ---
def create_nn_model(input_dim):
    model = Sequential([
        Input(shape=(input_dim,)),
        Dense(64, activation='relu'), Dropout(0.3),
        Dense(32, activation='relu'), Dropout(0.2),
        Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def train_oracle(X_train, y_train, X_test, y_test, preprocessor):
    print(f"\n=== Oracle Training for {TARGET_COLUMN} ===")
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)
    
    model = create_nn_model(X_train_proc.shape[1])
    es = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
    model.fit(X_train_proc, y_train, epochs=30, batch_size=32, validation_split=0.2, callbacks=[es], verbose=0)
    
    print("\nOracle Evaluation on Test Split (Final State):")
    y_pred = (model.predict(X_test_proc, verbose=0) > 0.5).astype(int)
    print(confusion_matrix(y_test, y_pred))
    print(classification_report(y_test, y_pred, zero_division=0))
    return model, preprocessor

# --- Simulation Helper Class (Rewinds State) with ENHANCED dynamic features ---
class CustomerState:
    def __init__(self, final_row_data):
        self.id = final_row_data['customer_id']
        self.static_props = final_row_data.to_dict()
        
        # Initial State Values
        self.current_balance = float(final_row_data['initial_avg_monthly_balance'])
        self.current_score = float(final_row_data['initial_credit_score'])
        
        # Rolling counts/spends for dynamic features
        self.txn_count_rolling = 0 
        self.high_value_count_rolling = 0
        self.bounced_count_rolling = 0
        self.fuel_spend_rolling = 0
        self.transport_spend_rolling = 0
        self.investment_debit_rolling = 0
        
        self.updates_since_trigger = 0
        
        # Pre-calc constants for Ratio calcs
        self.monthly_income = float(final_row_data['yearly_income']) / 12
        self.yearly_income = float(final_row_data['yearly_income'])
        self.emi = float(final_row_data['existing_loan_monthly_EMI_total'])
        self.credit_limit = float(final_row_data['total_credit_limit'])
        self.age = float(final_row_data['age'])
        self.dependents = float(final_row_data['dependents_count'])

    def apply_transaction(self, txn_row):
        amount = txn_row['txn_amount']
        bounced = txn_row['bounced_flag']
        category = txn_row['txn_category']
        
        self.current_balance += amount
        
        decay = 0.98 # Slower decay to represent monthly averages better
        self.txn_count_rolling = (self.txn_count_rolling * decay) + 1
        self.fuel_spend_rolling *= decay
        self.transport_spend_rolling *= decay
        self.investment_debit_rolling *= decay
        
        if abs(amount) > 75000: self.high_value_count_rolling = (self.high_value_count_rolling * decay) + 1
        else: self.high_value_count_rolling *= decay
            
        if bounced:
            self.bounced_count_rolling += 1
            self.current_score = max(300, self.current_score - 10)
        elif amount < 0:
             self.current_score = min(900, self.current_score + 0.5)
             # Add to rolling spends for debits
             if category == 'Fuel': self.fuel_spend_rolling += abs(amount)
             elif category == 'Transport': self.transport_spend_rolling += abs(amount)
             elif category == 'Investment': self.investment_debit_rolling += abs(amount)
        
        self.updates_since_trigger += 1

    def get_transient_features(self):
        feats = self.static_props.copy()
        
        # Update Dynamic Raw Values
        feats['final_avg_monthly_balance'] = self.current_balance
        feats['txn_count_last_30d'] = self.txn_count_rolling
        feats['high_value_txn_count_30d'] = self.high_value_count_rolling
        feats['bounced_txn_count'] = self.bounced_count_rolling
        feats['final_credit_score'] = self.current_score
        feats['monthly_fuel_spend'] = self.fuel_spend_rolling
        feats['monthly_transport_service_spend'] = self.transport_spend_rolling
        feats['avg_monthly_investment_debit'] = self.investment_debit_rolling
        
        # RE-CALCULATE RATIOS/INTERACTIONS
        feats['dti_ratio'] = self.emi / (self.monthly_income + 1)
        feats['savings_rate'] = self.current_balance / (self.monthly_income + 1)
        feats['income_to_limit'] = self.yearly_income / (self.credit_limit + 1)
        feats['txn_intensity'] = self.txn_count_rolling / (self.yearly_income / 10000 + 1)
        feats['age_x_dependents'] = self.age * self.dependents
        feats['score_x_log_income'] = self.current_score * np.log1p(self.yearly_income)

        return pd.Series(feats)

# --- Visualization Class ---
class SimVisualizer:
    def __init__(self, title_prefix):
        self.snapshots = []
        self.pca = None
        self.title_prefix = title_prefix

    def fit_pca(self, X):
        self.pca = PCA(n_components=2, random_state=42).fit(X)
    
    def capture(self, model, points, iter_num):
        self.snapshots.append({'iter': iter_num, 'means': [m.copy() for m in model.means], 'covs': [c.copy() for c in model.covariances], 'weights': model.weights.copy(), 'points': points.copy()})
        
    def save(self, filename):
        if not self.snapshots: return
        fig, ax = plt.subplots(figsize=(10,8))
        def update(i):
            ax.clear()
            d = self.snapshots[i]
            if len(d['points'])>0: ax.scatter(self.pca.transform(d['points'])[:,0], self.pca.transform(d['points'])[:,1], alpha=0.1, c='gray', s=5)
            for m, c, w in zip(d['means'], d['covs'], d['weights']):
                if w < 0.001: continue
                m2d = self.pca.transform(m.reshape(1,-1))[0]
                c2d = self.pca.components_ @ c @ self.pca.components_.T
                try:
                    v, vec = np.linalg.eigh(c2d)
                    ang = np.degrees(np.arctan2(vec[1,0], vec[0,0]))
                    w_ell, h_ell = 2*np.sqrt(np.abs(v)*5.991)
                    ax.add_patch(Ellipse(m2d, w_ell, h_ell, angle=ang, color='green', alpha=0.2, ec='darkgreen'))
                except np.linalg.LinAlgError:
                    pass # Covariance might not be perfectly invertible for viz
            ax.set_title(f"Txn Batch: {d['iter']} | {self.title_prefix} Clusters: {len(d['weights'])}")
            ax.set_xlabel("PCA 1 (Transient)"); ax.set_ylabel("PCA 2 (Transient)")
        ani = animation.FuncAnimation(fig, update, frames=len(self.snapshots), repeat=False)
        ani.save(filename, writer='pillow', fps=5)
        print(f"Animation saved to {filename}")

# --- Global State Container for Streaming ---
class StreamingState:
    def __init__(self):
        self.cust_states = {}
        self.stats = {'TP': 0, 'FP': 0, 'TN': 0, 'FN': 0, 'processed': 0}
        self.viz_buffer = []
        self.txn_counter = 0
        self.scaler = None
        self.ord_enc = None
        self.nn_preprocessor = None
        self.oracle = None
        self.gmm_model = None
        self.viz = None

    def initialize_customer(self, cust_row):
        """Initialize customer state from initial data"""
        if cust_row['customer_id'] not in self.cust_states:
            self.cust_states[cust_row['customer_id']] = CustomerState(cust_row)

    def process_transaction(self, txn_row):
        """Process a single transaction in streaming mode"""
        cid = txn_row['customer_id']
        if cid not in self.cust_states:
            return None

        self.cust_states[cid].apply_transaction(txn_row)
        self.txn_counter += 1

        # Check less frequently
        if self.cust_states[cid].updates_since_trigger >= 15:
            self.cust_states[cid].updates_since_trigger = 0

            curr_data = self.cust_states[cid].get_transient_features()
            df_row = pd.DataFrame([curr_data])

            x_num = self.scaler.transform(df_row[GMM_NUM_FEATURES])[0]
            x_cat = self.ord_enc.transform(df_row[GMM_CAT_FEATURES])[0]
            x_nn = self.nn_preprocessor.transform(df_row[NN_NUMERICAL_FEATURES + NN_CATEGORICAL_FEATURES])

            truth_prob = self.oracle.predict(x_nn, verbose=0)[0][0]
            truth_label = (truth_prob > 0.5)

            is_in, k, score, mahal_dists = self.gmm_model.predict_score(x_num, x_cat)
            self.gmm_model.update(x_num, x_cat, truth_label, (is_in, k, score, mahal_dists))

            if is_in and truth_label: self.stats['TP'] += 1
            elif is_in and not truth_label: self.stats['FP'] += 1
            elif not is_in and not truth_label: self.stats['TN'] += 1
            elif not is_in and truth_label: self.stats['FN'] += 1
            self.stats['processed'] += 1

            if truth_label: self.viz_buffer.append(x_num)

            if self.stats['processed'] % 200 == 0:
                self.viz.capture(self.gmm_model, np.array(self.viz_buffer), self.stats['processed'])
                self.viz_buffer = []

        if self.txn_counter % 5000 == 0:
            denom = self.stats['processed']
            if denom > 0:
                acc = (self.stats['TP'] + self.stats['TN']) / denom
                prec = self.stats['TP'] / (self.stats['TP'] + self.stats['FP']) if (self.stats['TP']+self.stats['FP']) > 0 else 0
                rec = self.stats['TP'] / (self.stats['TP'] + self.stats['FN']) if (self.stats['TP']+self.stats['FN']) > 0 else 0
                print(f"\n--- REPORT @ Txn {self.txn_counter} ---")
                print(f"Accuracy: {acc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f}")
                print(f"CM: [TN:{self.stats['TN']} FP:{self.stats['FP']}] [FN:{self.stats['FN']} TP:{self.stats['TP']}]")

        return True

# --- Main Execution ---
if __name__ == '__main__':
    # 1. Load Data for Training (Static Mode)
    print("=== Loading Initial Training Data ===")

    # Determine correct data path (works from both parent and experiment7_pathway directories)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)  # Parent directory

    init_data_path = os.path.join(data_dir, 'initial_training_data.csv')
    stream_cust_path = os.path.join(data_dir, 'streaming_customers_initial_state.csv')
    stream_txn_path = os.path.join(data_dir, 'streaming_transactions.csv')

    init_cust_df = pd.read_csv(init_data_path)
    stream_cust_df = pd.read_csv(stream_cust_path)

    print(f"Loaded {len(init_cust_df)} training customers and {len(stream_cust_df)} streaming customers.")

    # 2. Oracle Training
    nn_preprocessor = ColumnTransformer([
        ('num', StandardScaler(), NN_NUMERICAL_FEATURES),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), NN_CATEGORICAL_FEATURES)
    ], remainder='passthrough')

    oracle, nn_preprocessor = train_oracle(
        init_cust_df[NN_NUMERICAL_FEATURES + NN_CATEGORICAL_FEATURES], init_cust_df[TARGET_COLUMN],
        stream_cust_df[NN_NUMERICAL_FEATURES + NN_CATEGORICAL_FEATURES], stream_cust_df[TARGET_COLUMN],
        nn_preprocessor
    )

    # 3. GMM Initialization (ONE CLASS: ONLY POSITIVES)
    print(f"\n=== GMM Initialization for {TARGET_COLUMN} (Positive Class Only) ===")
    scaler = StandardScaler()
    ord_enc = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)

    scaler.fit(init_cust_df[GMM_NUM_FEATURES])
    ord_enc.fit(init_cust_df[GMM_CAT_FEATURES])
    cat_dims = [len(c) for c in ord_enc.categories_]

    positive_train_df = init_cust_df[init_cust_df[TARGET_COLUMN] == 1]

    X_init_num = scaler.transform(positive_train_df[GMM_NUM_FEATURES])
    X_init_cat = ord_enc.transform(positive_train_df[GMM_CAT_FEATURES])

    gmm_model = StreamingHybridAdvanced(X_init_num.shape[1], cat_dims, kMax=8, learning_rate=0.05)
    gmm_model.fit_batch(X_init_num, X_init_cat)
    print(f"GMM initialized with {gmm_model.n_components} components.")

    # 4. Setup Streaming Pipeline
    print(f"\n=== Setting Up Pathway Streaming Pipeline for {TARGET_COLUMN} ===")

    # Initialize global state
    state = StreamingState()
    state.scaler = scaler
    state.ord_enc = ord_enc
    state.nn_preprocessor = nn_preprocessor
    state.oracle = oracle
    state.gmm_model = gmm_model
    state.viz = SimVisualizer(GIF_TITLE_PREFIX)
    state.viz.fit_pca(scaler.transform(init_cust_df[GMM_NUM_FEATURES]))

    # Initialize customer states
    for _, row in stream_cust_df.iterrows():
        state.initialize_customer(row)

    # Define Pathway Schema for Transactions (matches TxnSchema from publisher)
    class TransactionSchema(pw.Schema):
        customer_id: str
        txn_datetime: str  # Will be str when reading from CSV
        txn_amount: float
        txn_type: str
        balance_after_txn: float
        bounced_flag: bool
        txn_category: str

    # Parse command-line arguments for mode selection
    parser = argparse.ArgumentParser(description='Run Home Loan simulation with Pathway')
    parser.add_argument('--mode', choices=['csv', 'nats'], default='csv',
                        help='Data source mode: csv (default) or nats')
    parser.add_argument('--nats-uri', default='nats://localhost:4222',
                        help='NATS server URI (only used in nats mode)')
    parser.add_argument('--nats-topic', default='transactions.stream',
                        help='NATS topic to subscribe to (only used in nats mode)')
    args = parser.parse_args()

    # Load streaming transactions using Pathway (CSV or NATS)
    print(f"Loading streaming transactions with Pathway (mode: {args.mode})...")

    if args.mode == 'csv':
        # Read from CSV file
        stream_txns_table = pw.io.csv.read(
            stream_txn_path,
            schema=TransactionSchema,
            mode='static'  # Use static mode to process all data like a stream
        )
    else:  # nats mode
        # Read from NATS stream
        print(f"Connecting to NATS at {args.nats_uri}, topic: {args.nats_topic}")
        stream_txns_table = pw.io.nats.read(
            uri=args.nats_uri,
            topic=args.nats_topic,
            format='json',
            schema=TransactionSchema
        )

    # Process each transaction using Pathway UDF
    @pw.udf
    def process_txn_udf(customer_id: str, txn_datetime: str, txn_amount: float,
                        txn_type: str, balance_after_txn: float, bounced_flag: bool,
                        txn_category: str) -> int:
        """Process transaction and return processing status
        Note: Only uses customer_id, txn_datetime, txn_amount, txn_category, bounced_flag
        """
        # Convert txn_datetime to string if it's a datetime object
        if isinstance(txn_datetime, datetime):
            txn_datetime = txn_datetime.isoformat()

        txn_row = {
            'customer_id': customer_id,
            'txn_datetime': txn_datetime,
            'txn_amount': txn_amount,
            'txn_category': txn_category,
            'bounced_flag': bool(bounced_flag)
        }
        result = state.process_transaction(txn_row)
        return 1 if result else 0

    # Apply processing to streaming table
    processed_table = stream_txns_table.select(
        customer_id=pw.this.customer_id,
        status=process_txn_udf(
            pw.this.customer_id,
            pw.this.txn_datetime,
            pw.this.txn_amount,
            pw.this.txn_type,
            pw.this.balance_after_txn,
            pw.this.bounced_flag,
            pw.this.txn_category
        )
    )

    # Write output (optional - can be used for debugging)
    pw.io.csv.write(processed_table, "pathway_output_home_loan.csv")

    # Run the Pathway pipeline
    print("Running Pathway streaming pipeline...")
    pw.run()

    # Final report
    print("\n=== Final Simulation Report ===")
    denom = state.stats['processed']
    acc = (state.stats['TP'] + state.stats['TN']) / denom if denom > 0 else 0
    prec = state.stats['TP'] / (state.stats['TP'] + state.stats['FP']) if (state.stats['TP']+state.stats['FP']) > 0 else 0
    rec = state.stats['TP'] / (state.stats['TP'] + state.stats['FN']) if (state.stats['TP']+state.stats['FN']) > 0 else 0
    print(f"Updates: {state.stats['processed']} | Accuracy: {acc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f}")

    state.viz.save(GIF_FILENAME)