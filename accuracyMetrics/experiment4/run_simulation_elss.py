# run_simulation_car_loan.py

import pandas as pd
import numpy as np
import os
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

# Custom imports
from streaming_hybrid_advanced import StreamingHybridAdvanced
from pipeline_config import ELSS_CONFIG # <-- Import the specific config

# --- Configuration from Imported Dictionary ---
CONFIG = ELSS_CONFIG
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

# --- Main Execution ---
if __name__ == '__main__':
    # 1. Load Data
    init_cust_df = pd.read_csv('initial_training_data.csv')
    stream_cust_df = pd.read_csv('streaming_customers_initial_state.csv')
    stream_txns = pd.read_csv('streaming_transactions.csv')
    stream_txns['txn_datetime'] = pd.to_datetime(stream_txns['txn_datetime'])
    stream_txns = stream_txns.sort_values('txn_datetime')
    
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
    
    # 4. Simulation
    print(f"\n=== Event-Driven Simulation for {TARGET_COLUMN} ===")
    viz = SimVisualizer(GIF_TITLE_PREFIX)
    viz.fit_pca(scaler.transform(init_cust_df[GMM_NUM_FEATURES])) 
    
    cust_states = {row['customer_id']: CustomerState(row) for _, row in stream_cust_df.iterrows()}
    stats = {'TP': 0, 'FP': 0, 'TN': 0, 'FN': 0, 'processed': 0}
    viz_buffer = []
    
    print(f"Simulating {len(stream_txns)} transactions...")
    
    for txn_counter, (_, txn) in enumerate(stream_txns.iterrows(), 1):
        cid = txn['customer_id']
        if cid not in cust_states: continue
        
        cust_states[cid].apply_transaction(txn)
        
        if cust_states[cid].updates_since_trigger >= 15: # Check less frequently
            cust_states[cid].updates_since_trigger = 0
            
            curr_data = cust_states[cid].get_transient_features()
            df_row = pd.DataFrame([curr_data])
            
            x_num = scaler.transform(df_row[GMM_NUM_FEATURES])[0]
            x_cat = ord_enc.transform(df_row[GMM_CAT_FEATURES])[0]
            x_nn = nn_preprocessor.transform(df_row[NN_NUMERICAL_FEATURES + NN_CATEGORICAL_FEATURES])

            truth_prob = oracle.predict(x_nn, verbose=0)[0][0]
            truth_label = (truth_prob > 0.5)

            is_in, k, score, mahal_dists = gmm_model.predict_score(x_num, x_cat)
            gmm_model.update(x_num, x_cat, truth_label, (is_in, k, score, mahal_dists))

            if is_in and truth_label: stats['TP'] += 1
            elif is_in and not truth_label: stats['FP'] += 1
            elif not is_in and not truth_label: stats['TN'] += 1
            elif not is_in and truth_label: stats['FN'] += 1
            stats['processed'] += 1
            
            if truth_label: viz_buffer.append(x_num)

            if stats['processed'] % 200 == 0: viz.capture(gmm_model, np.array(viz_buffer), stats['processed']); viz_buffer = []
        
        if txn_counter % 5000 == 0:
            denom = stats['processed']
            if denom > 0:
                acc = (stats['TP'] + stats['TN']) / denom
                prec = stats['TP'] / (stats['TP'] + stats['FP']) if (stats['TP']+stats['FP']) > 0 else 0
                rec = stats['TP'] / (stats['TP'] + stats['FN']) if (stats['TP']+stats['FN']) > 0 else 0
                print(f"\n--- REPORT @ Txn {txn_counter} ---")
                print(f"Accuracy: {acc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f}")
                print(f"CM: [TN:{stats['TN']} FP:{stats['FP']}] [FN:{stats['FN']} TP:{stats['TP']}]")

    print("\n=== Final Simulation Report ===")
    denom = stats['processed']
    acc = (stats['TP'] + stats['TN']) / denom if denom > 0 else 0
    prec = stats['TP'] / (stats['TP'] + stats['FP']) if (stats['TP']+stats['FP']) > 0 else 0
    rec = stats['TP'] / (stats['TP'] + stats['FN']) if (stats['TP']+stats['FN']) > 0 else 0
    print(f"Updates: {stats['processed']} | Accuracy: {acc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f}")
    
    viz.save(GIF_FILENAME)