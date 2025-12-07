# init_car_trainer.py
# Location: ./TargettedCalling/carLoanPredictor/init_car_trainer.py

import pandas as pd
import numpy as np
import os
from pathlib import Path
import sys
from datetime import datetime
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
import time

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
MONITORING_DIR = PARENT_DIR / "monitoring"
sys.path.append(str(PARENT_DIR))
sys.path.append(str(CURRENT_DIR))
sys.path.append(str(MONITORING_DIR))

# Imports
from models.online_GMM_v1 import onlineGMMv1
from persistenceUtils.persistence_utils import load_model_system,save_model_system
from pipelineConfigs.pipeline_configs import CAR_LOAN_CONFIG as CONFIG 

# Import metrics
try:
    from metrics import (
        record_training_samples,
        record_baseline_components,
        record_training_duration,
        record_feature_dimensions,
        record_training_status
    )
    METRICS_ENABLED = True
except ImportError:
    print("⚠️  Warning: metrics module not found. Metrics will not be recorded.")
    METRICS_ENABLED = False

# --- CONFIGURATION ---
TARGET = CONFIG["target"]
NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]
MODEL_SAVE_PATH = os.path.join(PARENT_DIR, "Persistence", "model_car.json")
DATA_FILE = os.path.join(PARENT_DIR, "MASTERFILE.csv")
LOG_ENABLED = True  # Set to False to disable logging
LOG_FILE = os.path.join(CURRENT_DIR, "init_trainer.log")

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

def train_and_save():
    training_start_time = time.time()
    training_success = False
    
    log_message("═══════════════════════════════════════════════")
    log_message(f"    Initializing Trainer for {TARGET}        ")
    log_message("═══════════════════════════════════════════════")
    log_message(f"Data File:      {DATA_FILE}")
    log_message(f"Model Path:     {MODEL_SAVE_PATH}")
    log_message(f"Log File:       {LOG_FILE if LOG_ENABLED else 'DISABLED'}")
    log_message(f"Metrics:        {'ENABLED' if METRICS_ENABLED else 'DISABLED'}")
    log_message("═══════════════════════════════════════════════\n")
    
    try:
        # 1. Load Data
        if not os.path.exists(DATA_FILE):
            raise FileNotFoundError(f"{DATA_FILE} not found.")
        
        log_message(f"Loading data from {DATA_FILE}...")
        df = pd.read_csv(DATA_FILE)
        log_message(f"✓ Data loaded. Total rows: {len(df)}")
        
        # 2. Filter for Relevant Training Rows
        positive_df = df[df[TARGET] == 1].copy()
        
        log_message(f"\nTraining Data Statistics:")
        log_message(f"  Total Rows: {len(df)}")
        log_message(f"  Positive Samples (target=1): {len(positive_df)}")
        log_message(f"  Negative/Streaming Samples (target=0): {len(df) - len(positive_df)}")

        if len(positive_df) == 0:
            log_message("❌ ERROR: No positive samples found. Cannot train.")
            if METRICS_ENABLED:
                record_training_samples(0)
                record_training_status(False)
            return

        # 📊 METRIC: Record training sample count
        if METRICS_ENABLED:
            record_training_samples(len(positive_df))
            log_message(f"📊 Metric recorded: Training samples = {len(positive_df)}")

        # 3. Fit Preprocessors
        log_message("\n📊 Fitting Preprocessors...")
        log_message(f"  Numerical Features ({len(NUM_FEATURES)}): {NUM_FEATURES}")
        log_message(f"  Categorical Features ({len(CAT_FEATURES)}): {CAT_FEATURES}")
        
        # 📊 METRIC: Record feature dimensions
        if METRICS_ENABLED:
            record_feature_dimensions(len(NUM_FEATURES), len(CAT_FEATURES))
            log_message(f"📊 Metric recorded: Feature dimensions = {len(NUM_FEATURES)} num, {len(CAT_FEATURES)} cat")
        
        scaler = StandardScaler()
        X_num = scaler.fit_transform(positive_df[NUM_FEATURES])
        log_message(f"  ✓ StandardScaler fitted on {X_num.shape[0]} samples")

        ord_enc = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
        X_cat = ord_enc.fit_transform(positive_df[CAT_FEATURES])
        
        cat_dims = [len(c) for c in ord_enc.categories_]
        log_message(f"  ✓ OrdinalEncoder fitted. Category dimensions: {cat_dims}")
        
        # 4. Initialize and Fit GMM
        log_message("\n🧠 Fitting StreamingHybridAdvanced GMM...")
        X_meta = positive_df['customer_id'].tolist()
        
        model = onlineGMMv1(
            num_dim=X_num.shape[1], 
            cat_dims=cat_dims, 
            kMax=20, 
            learning_rate=0.05, 
            max_exemplars=6
        )
        
        log_message(f"  Model Configuration:")
        log_message(f"    - Numerical Dimensions: {X_num.shape[1]}")
        log_message(f"    - Categorical Dimensions: {len(cat_dims)}")
        log_message(f"    - Max Components (kMax): 8")
        log_message(f"    - Learning Rate: 0.05")
        log_message(f"    - Max Exemplars per Cluster: 6")
        
        model.fit_batch(X_num, X_cat, X_meta=X_meta)
        log_message(f"  ✓ Model Initialized. Components: {model.n_components}")

        # 📊 METRIC: Record baseline components
        if METRICS_ENABLED:
            record_baseline_components(model.n_components)
            log_message(f"📊 Metric recorded: Baseline components = {model.n_components}")

        # 5. Save to JSON
        log_message(f"\n💾 Saving model system to {MODEL_SAVE_PATH}...")
        
        # Ensure Persistence directory exists
        os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
        
        save_model_system(model, scaler, ord_enc, MODEL_SAVE_PATH)
        log_message("✓ Model system saved successfully!")
        
        training_success = True
        
        # 6. Summary
        training_duration = time.time() - training_start_time
        
        # 📊 METRIC: Record training duration and status
        if METRICS_ENABLED:
            record_training_duration(training_duration)
            record_training_status(True)
            log_message(f"📊 Metric recorded: Training duration = {training_duration:.2f}s")
            log_message(f"📊 Metric recorded: Training status = SUCCESS")
        
        log_message("\n" + "="*50)
        log_message("TRAINING COMPLETE - SUMMARY")
        log_message("="*50)
        log_message(f"Training Samples:     {len(positive_df)}")
        log_message(f"GMM Components:       {model.n_components}")
        log_message(f"Training Duration:    {training_duration:.2f}s")
        log_message(f"Model Location:       {MODEL_SAVE_PATH}")
        log_message(f"Log Location:         {LOG_FILE}")
        log_message(f"Metrics Recorded:     {'YES' if METRICS_ENABLED else 'NO'}")
        log_message("="*50 + "\n")
        
    except Exception as e:
        log_message(f"\n❌ TRAINING FAILED: {e}")
        import traceback
        log_message(traceback.format_exc())
        
        # 📊 METRIC: Record failure
        if METRICS_ENABLED:
            record_training_status(False)
            training_duration = time.time() - training_start_time
            record_training_duration(training_duration)
            log_message(f"📊 Metric recorded: Training status = FAILED")

if __name__ == "__main__":
    train_and_save()