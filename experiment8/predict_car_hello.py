# predict_car_hello.py

import pandas as pd
import numpy as np
import os

# Imports
from streaming_hybrid_advanced import StreamingHybridAdvanced
from persistence_utils import load_model_system
from pipeline_config import CAR_LOAN_CONFIG as CONFIG

# --- CONFIGURATION ---
TARGET = CONFIG["target"]
NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]
MODEL_LOAD_PATH = os.path.join("persistence", "model_car.json")
DATA_FILE = "MASTERFILE.csv"

def predict_hello():
    print(f"=== Prediction 'Hello' for {TARGET} ===")

    # 1. Load Model and Preprocessors
    if not os.path.exists(MODEL_LOAD_PATH):
        print(f"Error: Model file {MODEL_LOAD_PATH} not found. Run init_car_trainer.py first.")
        return

    print(f"Loading model from {MODEL_LOAD_PATH}...")
    model, scaler, ord_enc = load_model_system(MODEL_LOAD_PATH)
    print(f"Model Loaded. Components: {model.n_components}")

    # 2. Load Data
    print(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)

    # Let's predict on the last 10 rows (Streaming data) to verify
    # In a real scenario, you might read row by row or a specific batch
    sample_df = df.tail(10).copy() 

    # 3. Preprocess Input
    # Note: ordinal encoder expects 2D array, even for one row
    try:
        X_num = scaler.transform(sample_df[NUM_FEATURES])
        X_cat = ord_enc.transform(sample_df[CAT_FEATURES])
    except Exception as e:
        print(f"Preprocessing Error: {e}")
        return

    # 4. Predict
    print("\n--- Predictions on last 10 rows of MASTERFILE ---")
    print(f"{'Cust ID':<15} | {'Score':<10} | {'Cluster':<8} | {'Exemplars (IDs of similar past users)'}")
    print("-" * 100)

    for i in range(len(sample_df)):
        cust_id = sample_df.iloc[i]['customer_id']
        x_n = X_num[i]
        x_c = X_cat[i]

        # Predict Score
        is_in, k, score, mahal, exemplars = model.predict_score(x_n, x_c)

        # Formatting Output
        score_str = f"{score:.2f}"
        cluster_str = str(k) if k != -1 else "Noise"
        ex_str = str(exemplars) if exemplars else "[]"
        
        # Highlight matches
        prefix = ">>> " if is_in else "    "
        
        print(f"{prefix}{cust_id:<11} | {score_str:<10} | {cluster_str:<8} | {ex_str}")

    print("\nPrediction Run Complete.")

if __name__ == "__main__":
    predict_hello()