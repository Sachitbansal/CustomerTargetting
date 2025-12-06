# init_car_trainer.py

import pandas as pd
import numpy as np
import os
from sklearn.preprocessing import StandardScaler, OrdinalEncoder

# Imports
from streaming_hybrid_advanced import StreamingHybridAdvanced
from persistence_utils import save_model_system
from pipeline_config import CAR_LOAN_CONFIG as CONFIG 

# --- CONFIGURATION ---
TARGET = CONFIG["target"]
NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]
MODEL_SAVE_PATH = os.path.join("persistence", "model_car.json")
DATA_FILE = "MASTERFILE.csv"

def train_and_save():
    print(f"=== Initializing Trainer for {TARGET} ===")
    
    # 1. Load Data
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} not found.")
    
    df = pd.read_csv(DATA_FILE)
    
    # 2. Filter for Relevant Training Rows
    # Logic: We only train the One-Class GMM on Positive samples.
    # In MASTERFILE, streaming rows have target=0, so this filter 
    # automatically isolates the valid positive training data.
    positive_df = df[df[TARGET] == 1].copy()
    
    print(f"Total Rows: {len(df)}")
    print(f"Training on Positive Samples: {len(positive_df)}")

    if len(positive_df) == 0:
        print("Error: No positive samples found. Cannot train.")
        return

    # 3. Fit Preprocessors
    print("Fitting Preprocessors...")
    scaler = StandardScaler()
    X_num = scaler.fit_transform(positive_df[NUM_FEATURES])

    ord_enc = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
    X_cat = ord_enc.fit_transform(positive_df[CAT_FEATURES])
    
    cat_dims = [len(c) for c in ord_enc.categories_]
    
    # 4. Initialize and Fit GMM
    print("Fitting StreamingHybridAdvanced GMM...")
    # Extract IDs for exemplars
    X_meta = positive_df['customer_id'].tolist()
    
    model = StreamingHybridAdvanced(
        num_dim=X_num.shape[1], 
        cat_dims=cat_dims, 
        kMax=8, 
        learning_rate=0.05, 
        max_exemplars=6
    )
    
    model.fit_batch(X_num, X_cat, X_meta=X_meta)
    print(f"Model Initialized. Components: {model.n_components}")

    # 5. Save to JSON
    print(f"Saving artifacts to {MODEL_SAVE_PATH}...")
    save_model_system(model, scaler, ord_enc, MODEL_SAVE_PATH)
    print("Done.")

if __name__ == "__main__":
    train_and_save()