# car_loan_feedback_node.py
# Location: ./TargettedCalling/carLoanPredictor/car_loan_feedback_node.py

import pathway as pw
import pandas as pd
import numpy as np
import os
from pathlib import Path
import sys
from collections import deque
import threading
import time
from datetime import datetime

# --- PATH SETUP ---

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))

from persistenceUtils.persistence_utils import load_model_system, save_model_system
from pipelineConfigs.pipeline_configs import CAR_LOAN_CONFIG as CONFIG

# --- CONFIGURATION ---
NATS_URI = "nats://localhost:4222"
FEEDBACK_TOPIC = "feedback.carLoan"
MODEL_PATH = os.path.join(PARENT_DIR, "Persistence", "model_car.json")
MASTERFILE_PATH = os.path.join(PARENT_DIR, "MASTERFILE.csv")
LOG_ENABLED = True  # Set to False to disable logging
LOG_FILE = os.path.join(CURRENT_DIR, "feedback_node.log")

NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]

# Batch processing config
FEEDBACK_BATCH_SIZE = 5
AUTO_SAVE_INTERVAL = 30

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

class FeedbackProcessor:
    """Manages batched feedback updates to the GMM model"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.encoder = None
        self.feedback_buffer = deque()
        self.masterfile_df = None
        self.update_count = 0
        self.positive_feedback_count = 0
        self.negative_feedback_count = 0
        self.last_save_time = time.time()
        self.lock = threading.Lock()
        
        # Load initial state
        self.load_model()
        self.load_masterfile()
    
    def load_model(self):
        """Load model from disk"""
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
        
        log_message(f"Loading model from {MODEL_PATH}...")
        self.model, self.scaler, self.encoder = load_model_system(MODEL_PATH)
        log_message(f"✓ Model loaded. Components: {self.model.n_components}")
    
    def load_masterfile(self):
        """Load MASTERFILE for feature lookup"""
        if not os.path.exists(MASTERFILE_PATH):
            raise FileNotFoundError(f"MASTERFILE not found at {MASTERFILE_PATH}")
        
        log_message(f"Loading MASTERFILE from {MASTERFILE_PATH}...")
        self.masterfile_df = pd.read_csv(MASTERFILE_PATH)
        self.masterfile_df.set_index('customer_id', inplace=True)
        log_message(f"✓ MASTERFILE loaded. {len(self.masterfile_df)} customers indexed.")
    
    def save_model(self):
        """Save model to disk"""
        log_message(f"\n💾 Saving model after {self.update_count} updates...")
        save_model_system(self.model, self.scaler, self.encoder, MODEL_PATH)
        self.last_save_time = time.time()
        log_message(f"✓ Model saved to {MODEL_PATH}")
        log_message(f"✓ Current state: Components={self.model.n_components}, Positive={self.positive_feedback_count}, Negative={self.negative_feedback_count}\n")
    
    def process_feedback(self, customer_id, bought_loan):
        """Add feedback to buffer and process if batch is full"""
        log_message(f"📥 RECEIVED FEEDBACK | Customer: {customer_id} | Bought: {bought_loan}")
        
        with self.lock:
            self.feedback_buffer.append({
                'customer_id': customer_id,
                'bought_loan': bought_loan
            })
            
            log_message(f"Buffer size: {len(self.feedback_buffer)}/{FEEDBACK_BATCH_SIZE}")
            
            # Check if we should process the batch
            should_process = (
                len(self.feedback_buffer) >= FEEDBACK_BATCH_SIZE or
                (time.time() - self.last_save_time) >= AUTO_SAVE_INTERVAL
            )
            
            if should_process:
                self._process_batch()
        
        # Return a simple string for tracking
        return f"processed_{customer_id}"
    
    def _process_batch(self):
        """Process all feedback in buffer and update model"""
        if len(self.feedback_buffer) == 0:
            return
        
        log_message(f"\n{'='*60}")
        log_message(f"🔄 Processing batch of {len(self.feedback_buffer)} feedback points")
        log_message(f"{'='*60}")
        
        batch_data = list(self.feedback_buffer)
        self.feedback_buffer.clear()
        
        success_count = 0
        error_count = 0
        
        for feedback in batch_data:
            customer_id = feedback['customer_id']
            bought_loan = feedback['bought_loan']
            
            try:
                # Look up customer features from MASTERFILE
                if customer_id not in self.masterfile_df.index:
                    log_message(f"⚠ ERROR | Customer {customer_id} not found in MASTERFILE. Skipping.")
                    error_count += 1
                    continue
                
                row = self.masterfile_df.loc[customer_id]
                
                # Extract and preprocess features
                num_vals = [row[feat] for feat in NUM_FEATURES]
                cat_vals = [row[feat] for feat in CAT_FEATURES]
                
                df_num = pd.DataFrame([num_vals], columns=NUM_FEATURES)
                df_cat = pd.DataFrame([cat_vals], columns=CAT_FEATURES)
                
                x_num = self.scaler.transform(df_num)[0]
                x_cat = self.encoder.transform(df_cat)[0]
                
                # Get current prediction for context
                result_tuple = self.model.predict_score(x_num, x_cat)
                is_in, k, score, _, _ = result_tuple
                
                # Update model with feedback
                self.model.update(x_num, x_cat, bought_loan, result_tuple, meta=customer_id)
                
                self.update_count += 1
                success_count += 1
                
                # Track statistics
                if bought_loan:
                    self.positive_feedback_count += 1
                    feedback_type = "✓ POSITIVE"
                else:
                    self.negative_feedback_count += 1
                    feedback_type = "✗ NEGATIVE"
                
                log_message(f"{feedback_type} | Customer: {customer_id} | Cluster: {k} | Score: {score:.2f} | Update #{self.update_count}")
                
            except Exception as e:
                log_message(f"⚠ ERROR | Failed to process feedback for {customer_id}: {e}")
                error_count += 1
        
        # Save updated model
        if success_count > 0:
            self.save_model()
            log_message(f"✓ Batch complete: {success_count} updates, {error_count} errors")
        else:
            log_message(f"⚠ Batch failed: No successful updates")

# Global processor instance
processor = FeedbackProcessor()

def run_feedback_node():
    log_message("═══════════════════════════════════════════════")
    log_message("    CAR LOAN FEEDBACK NODE (PATHWAY)          ")
    log_message("═══════════════════════════════════════════════")
    log_message(f"Feedback Topic: {FEEDBACK_TOPIC}")
    log_message(f"Model Path:     {MODEL_PATH}")
    log_message(f"MASTERFILE:     {MASTERFILE_PATH}")
    log_message(f"Log File:       {LOG_FILE if LOG_ENABLED else 'DISABLED'}")
    log_message(f"Batch Config:   Update every {FEEDBACK_BATCH_SIZE} feedbacks")
    log_message(f"Auto-save:      Every {AUTO_SAVE_INTERVAL} seconds")
    log_message("═══════════════════════════════════════════════\n")
    
    # Expected schema: customer_id (str), custBoughtLoanOrNot (bool)
    class FeedbackSchema(pw.Schema):
        customer_id: str
        custBoughtLoanOrNot: bool
    
    # 1. Read feedback from NATS
    feedback_stream = pw.io.nats.read(
        uri=NATS_URI,
        topic=FEEDBACK_TOPIC,
        format="json",
        schema=FeedbackSchema
    )
    
    log_message(f"✓ Listening for feedback on '{FEEDBACK_TOPIC}'...")
    log_message(f"✓ LISTENING TO: {FEEDBACK_TOPIC}\n")
    
    # 2. Process each feedback point
    processed = feedback_stream.select(
        customer_id=pw.this.customer_id,
        status=pw.apply_with_type(
            lambda cid, bought: processor.process_feedback(cid, bought),
            str,
            pw.this.customer_id,
            pw.this.custBoughtLoanOrNot
        )
    )
    
    pw.io.null.write(processed)
    
    log_message("✓ Car Loan Feedback Node is running.\n")
    pw.run()

if __name__ == "__main__":
    run_feedback_node()