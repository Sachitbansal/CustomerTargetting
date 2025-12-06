# car_loan_prediction_node.py
# Location: ./TargettedCalling/carLoanPredictor/car_loan_prediction_node.py

import pathway as pw
import pandas as pd
import numpy as np
import os
from pathlib import Path
import sys
from datetime import datetime
import json
import time

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
MONITORING_DIR = PARENT_DIR / "monitoring"
sys.path.append(str(PARENT_DIR))
sys.path.append(str(CURRENT_DIR))
sys.path.append(str(MONITORING_DIR))

# Import MasterSchema from dataUpdater
from dataUpdater.schema import MasterSchema
from persistenceUtils.persistence_utils import load_model_system
from pipelineConfigs.pipeline_configs import CAR_LOAN_CONFIG as CONFIG

# Import metrics
try:
    from metrics import (
        initialize_metrics,
        record_prediction,
        record_inference_time,
        record_lead_qualification,
        record_car_loan_funnel,
        record_call_api_attempt,
        record_node_to_node_latency,
        update_qualified_leads_count,
        update_memory_usage,
        MetricsTimer
    )
    METRICS_ENABLED = True
except ImportError:
    print("⚠️  Warning: metrics module not found. Metrics will not be recorded.")
    METRICS_ENABLED = False

# --- CONFIGURATION ---
NATS_URI = "nats://localhost:4222"
INPUT_TOPIC = "leads.checkCarLoan"
OUTPUT_TOPIC = "leads.callCarLoan"
MODEL_PATH = os.path.join(PARENT_DIR, "Persistence", "model_car.json")
LOG_ENABLED = True  # Set to False to disable logging
LOG_FILE = os.path.join(CURRENT_DIR, "prediction_node.log")
METRICS_PORT = 8005  # Dedicated port for predictor metrics

NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]

# Batch processing config
PREDICTION_BATCH_SIZE = 10
MODEL_RELOAD_INTERVAL = 100

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

class CarLoanPredictor:
    """Singleton predictor that manages model state and batch reloading"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.encoder = None
        self.prediction_count = 0
        self.qualified_count = 0
        self.rejected_count = 0
        self.model_load_count = 0
        self.load_model()
    
    def load_model(self):
        """Load model from disk"""
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run init_car_trainer.py first.")
        
        log_message(f"Loading model from {MODEL_PATH}...")
        self.model, self.scaler, self.encoder = load_model_system(MODEL_PATH)
        self.model_load_count += 1
        log_message(f"✓ Model loaded (Load #{self.model_load_count}). Components: {self.model.n_components}")
    
    def should_reload_model(self):
        """Check if we should reload the model from disk"""
        return self.prediction_count % MODEL_RELOAD_INTERVAL == 0 and self.prediction_count > 0
    
    def predict(self, customer_id, *features):
        """Make prediction for a single customer"""
        # Reload model periodically to catch feedback updates
        if self.should_reload_model():
            log_message(f"⟳ Reloading model after {self.prediction_count} predictions...")
            self.load_model()
        
        self.prediction_count += 1
        inference_start = time.time()
        
        try:
            # Split into numerical and categorical based on CONFIG
            num_vals = list(features[:len(NUM_FEATURES)])
            cat_vals = list(features[len(NUM_FEATURES):])
            
            # Preprocess
            df_num = pd.DataFrame([num_vals], columns=NUM_FEATURES)
            df_cat = pd.DataFrame([cat_vals], columns=CAT_FEATURES)
            
            x_num = self.scaler.transform(df_num)[0]
            x_cat = self.encoder.transform(df_cat)[0]
            
            # Predict - now returns exemplars too!
            is_in, k, score, _, exemplars = self.model.predict_score(x_num, x_cat)
            
            # 📊 METRIC: Record inference time
            inference_duration = time.time() - inference_start
            if METRICS_ENABLED:
                record_inference_time(inference_duration)
            
            # Convert exemplars list to JSON string
            exemplars_str = json.dumps(exemplars) if exemplars else "[]"
            
            # Track statistics and record metrics
            if is_in:
                self.qualified_count += 1
                log_message(f"✓ PREDICTED YES | Customer: {customer_id} | Cluster: {k} | Score: {score:.2f} | "
                          f"Exemplars: {exemplars} | Total Predicted Yes: {self.qualified_count}")
                
                # 📊 METRIC: Record ML qualification and call attempt
                if METRICS_ENABLED:
                    record_lead_qualification('car_loan', 'ml_approved')
                    record_car_loan_funnel('ml_qualified')
                    record_call_api_attempt('car_loan')
                    update_qualified_leads_count('car_loan', self.qualified_count)
                    record_prediction(qualified=True, cluster_id=k, confidence=score, exemplar_count=len(exemplars) if exemplars else 0)
            else:
                self.rejected_count += 1
                log_message(f"✗ PREDICTED NO | Customer: {customer_id} | Cluster: {k} | Score: {score:.2f} | Total Predicted No: {self.rejected_count}")
                
                # 📊 METRIC: Record rejection
                if METRICS_ENABLED:
                    record_prediction(qualified=False, cluster_id=k, confidence=score, exemplar_count=0)
            
            # Return as pipe-delimited string with exemplars
            return f"{customer_id}|{int(is_in)}|{k}|{score}|{exemplars_str}"
            
        except Exception as e:
            log_message(f"⚠ ERROR | Prediction failed for customer {customer_id}: {e}")
            import traceback
            log_message(traceback.format_exc())
            return f"{customer_id}|0|-1|0.0|[]"

# Global predictor instance
predictor = CarLoanPredictor()

def run_prediction_node():
    log_message("═══════════════════════════════════════════════")
    log_message("    CAR LOAN PREDICTION NODE (PATHWAY)        ")
    log_message("═══════════════════════════════════════════════")
    log_message(f"Input Topic:  {INPUT_TOPIC}")
    log_message(f"Output Topic: {OUTPUT_TOPIC}")
    log_message(f"Model Path:   {MODEL_PATH}")
    log_message(f"Log File:     {LOG_FILE if LOG_ENABLED else 'DISABLED'}")
    log_message(f"Metrics:      {'ENABLED on port ' + str(METRICS_PORT) if METRICS_ENABLED else 'DISABLED'}")
    log_message(f"Batch Config: Reload every {MODEL_RELOAD_INTERVAL} predictions")
    log_message("═══════════════════════════════════════════════\n")
    
    # 📊 Initialize metrics server
    if METRICS_ENABLED:
        try:
            metrics_manager = initialize_metrics("ml_car_predictor", port=METRICS_PORT)
            log_message(f"✓ Metrics server initialized on port {METRICS_PORT}")
        except Exception as e:
            log_message(f"⚠️  Failed to initialize metrics: {e}")
    
    # 1. Read from NATS topic with MasterSchema
    input_stream = pw.io.nats.read(
        uri=NATS_URI,
        topic=INPUT_TOPIC,
        format="json",
        schema=MasterSchema
    )
    
    log_message(f"✓ Listening for car loan leads on '{INPUT_TOPIC}'...")
    
    # 2. Build feature columns
    feature_cols = []
    for feat in NUM_FEATURES:
        feature_cols.append(pw.this[feat])
    for feat in CAT_FEATURES:
        feature_cols.append(pw.this[feat])
    
    # 3. Apply prediction - returns pipe-delimited string with exemplars
    with_prediction = input_stream.select(
        pw.this.customer_id,
        prediction_str=pw.apply_with_type(
            lambda cid, *feats: predictor.predict(cid, *feats),
            str,
            pw.this.customer_id,
            *feature_cols
        )
    )
    
    # 4. Parse the prediction string
    all_predictions = with_prediction.select(
        customer_id=pw.this.customer_id,
        predicted_eligible=pw.apply_with_type(
            lambda s: bool(int(s.split('|')[1])),
            bool,
            pw.this.prediction_str
        ),
        cluster_id=pw.apply_with_type(
            lambda s: int(s.split('|')[2]),
            int,
            pw.this.prediction_str
        ),
        confidence_score=pw.apply_with_type(
            lambda s: float(s.split('|')[3]),
            float,
            pw.this.prediction_str
        ),
        similar_customers=pw.apply_with_type(
            lambda s: s.split('|')[4] if len(s.split('|')) > 4 else "[]",
            str,
            pw.this.prediction_str
        )
    )
    
    # 5. Stream ALL predictions (both yes and no) to tester
    log_message(f"✓ Publishing ALL predictions (qualified + rejected) to '{OUTPUT_TOPIC}'...")
    
    # 6. Write all predictions to output topic
    pw.io.nats.write(
        all_predictions,
        uri=NATS_URI,
        topic=OUTPUT_TOPIC,
        format="json"
    )
    
    log_message(f"✓ STREAMING TO: {OUTPUT_TOPIC}")
    log_message("\n✓ Car Loan Prediction Node is running.\n")
    pw.run()

if __name__ == "__main__":
    run_prediction_node()