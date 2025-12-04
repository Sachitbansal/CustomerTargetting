# predict_car.py
# Location: ./TargettedCalling/carLoanPredictor/predict_car.py

import pandas as pd
import numpy as np
import os
from pathlib import Path
import sys
from datetime import datetime

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))
sys.path.append(str(CURRENT_DIR))

# Imports
from streaming_hybrid_advanced import StreamingHybridAdvanced
from persistence_utils import load_model_system
from pipeline_config import CAR_LOAN_CONFIG as CONFIG

# --- CONFIGURATION ---
TARGET = CONFIG["target"]
NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]
MODEL_PATH = os.path.join(PARENT_DIR, "Persistence", "model_car.json")
DATA_FILE = os.path.join(PARENT_DIR, "MASTERFILE.csv")
LOG_ENABLED = True  # Set to False to disable logging
LOG_FILE = os.path.join(CURRENT_DIR, "predict_car.log")

def log_message(message):
    """Log message to file if logging is enabled"""
    if LOG_ENABLED:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry)
        print(message)
    else:
        print(message)

def run_prediction():
    log_message("═══════════════════════════════════════════════")
    log_message(f"      Running Prediction for {TARGET}        ")
    log_message("═══════════════════════════════════════════════")
    log_message(f"Model Path:     {MODEL_PATH}")
    log_message(f"Data File:      {DATA_FILE}")
    log_message(f"Log File:       {LOG_FILE if LOG_ENABLED else 'DISABLED'}")
    log_message("═══════════════════════════════════════════════\n")

    # 1. Load Model System
    if not os.path.exists(MODEL_PATH):
        log_message(f"❌ ERROR: {MODEL_PATH} not found. Initialize it first.")
        return

    log_message("Loading model state...")
    model, scaler, ord_enc = load_model_system(MODEL_PATH)
    log_message(f"✓ Model loaded. Components: {model.n_components}\n")

    # 2. Load Data
    log_message(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    
    # Pick a random row from the end (simulating a recent customer)
    random_idx = np.random.randint(max(0, len(df) - 50), len(df))
    row = df.iloc[random_idx]
    
    cust_id = row['customer_id']
    log_message(f"✓ Selected random customer: {cust_id} (row {random_idx})\n")
    
    # 3. Preprocess Input
    log_message("Preprocessing customer data...")
    try:
        df_num = pd.DataFrame([row[NUM_FEATURES].values], columns=NUM_FEATURES)
        df_cat = pd.DataFrame([row[CAT_FEATURES].values], columns=CAT_FEATURES)
        
        x_num = scaler.transform(df_num)[0]
        x_cat = ord_enc.transform(df_cat)[0]
        log_message("✓ Preprocessing complete\n")
    except Exception as e:
        log_message(f"❌ Preprocessing failed: {e}")
        return

    # 4. Make Prediction
    log_message("Making prediction...")
    result_tuple = model.predict_score(x_num, x_cat)
    is_in, k, score, _, _ = result_tuple
    
    # 5. Display Results
    log_message("="*50)
    log_message("PREDICTION RESULTS")
    log_message("="*50)
    log_message(f"Customer ID:        {cust_id}")
    log_message(f"Eligible:           {'✓ YES' if is_in else '✗ NO'}")
    log_message(f"Assigned Cluster:   {k}")
    log_message(f"Confidence Score:   {score:.4f}")
    log_message(f"In Distribution:    {is_in}")
    log_message("="*50 + "\n")
    
    # 6. Additional Info
    if is_in and k >= 0:
        log_message(f"Cluster {k} exemplars: {model.exemplars[k]}")
    
    log_message("\nPrediction complete.")

if __name__ == "__main__":
    run_prediction()