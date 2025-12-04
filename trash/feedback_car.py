# feedback_car.py
# Location: ./TargettedCalling/carLoanPredictor/feedback_car.py

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
from persistence_utils import load_model_system, save_model_system
from pipeline_config import CAR_LOAN_CONFIG as CONFIG

# --- CONFIGURATION ---
TARGET = CONFIG["target"]
NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]
MODEL_PATH = os.path.join(PARENT_DIR, "Persistence", "model_car.json")
DATA_FILE = os.path.join(PARENT_DIR, "MASTERFILE.csv")
LOG_ENABLED = True  # Set to False to disable logging
LOG_FILE = os.path.join(CURRENT_DIR, "feedback_simulation.log")

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

def run_feedback_simulation():
    log_message("═══════════════════════════════════════════════")
    log_message(f"  Running Online Learning (Feedback) for {TARGET}")
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
    
    # Snapshot state for comparison
    initial_components = model.n_components
    initial_weight_sum = np.sum(model.weights)
    log_message(f"✓ State loaded.")
    log_message(f"  Components: {initial_components}")
    log_message(f"  Total Weight: {initial_weight_sum:.4f}\n")

    # 2. Simulate an Incoming Data Point with Feedback
    log_message(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    
    # Pick a random row from the end (simulating a recent customer)
    random_idx = np.random.randint(max(0, len(df) - 50), len(df))
    row = df.iloc[random_idx]
    
    cust_id = row['customer_id']
    log_message(f"✓ Selected customer: {cust_id} (row {random_idx})\n")
    
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

    # 4. Simulate Ground Truth
    actual_feedback_label = np.random.choice([True, False])
    feedback_str = 'ACCEPTED (Positive Feedback)' if actual_feedback_label else 'REJECTED (Negative Feedback)'
    
    log_message("="*50)
    log_message("FEEDBACK SIMULATION")
    log_message("="*50)
    log_message(f"Customer ID:          {cust_id}")
    log_message(f"Simulated Decision:   {feedback_str}")
    log_message("="*50 + "\n")

    # 5. The Update Cycle
    log_message("Getting model prediction (before update)...")
    result_tuple = model.predict_score(x_num, x_cat)
    is_in, k, score, _, _ = result_tuple
    
    log_message(f"Model Prediction:")
    log_message(f"  Cluster: {k}")
    log_message(f"  Score: {score:.2f}")
    log_message(f"  In-Distribution: {is_in}\n")

    # Step B: UPDATE
    log_message("Updating model with feedback...")
    model.update(x_num, x_cat, actual_feedback_label, result_tuple, meta=cust_id)
    log_message("✓ Model updated\n")
    
    # 6. Save Updated Model
    log_message(f"Saving updated model to {MODEL_PATH}...")
    save_model_system(model, scaler, ord_enc, MODEL_PATH)
    log_message("✓ Model saved successfully\n")
    
    # 7. Verification
    log_message("="*50)
    log_message("UPDATE SUMMARY")
    log_message("="*50)
    log_message(f"Previous Components:  {initial_components}")
    log_message(f"New Components:       {model.n_components}")
    log_message(f"Feedback Type:        {'POSITIVE' if actual_feedback_label else 'NEGATIVE'}")
    
    if model.n_components > 0 and is_in and actual_feedback_label and k != -1:
        log_message(f"Updated Exemplars for Cluster {k}: {model.exemplars[k]}")
    
    log_message("="*50 + "\n")
    log_message("Feedback simulation complete.\n")

if __name__ == "__main__":
    run_feedback_simulation()