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
MONITORING_DIR = PARENT_DIR / "monitoring"
sys.path.append(str(PARENT_DIR))
sys.path.append(str(MONITORING_DIR))

from persistenceUtils.persistence_utils import load_model_system, save_model_system
from pipelineConfigs.pipeline_configs import CAR_LOAN_CONFIG as CONFIG

# Import metrics
try:
    from metrics import (
        initialize_metrics,
        record_feedback,
        update_model_components,
        record_update_time,
        record_save_time,
        update_feedback_buffer_size,
        update_time_since_save,
        record_feedback_error,
        record_batch_update,
        update_memory_usage,
        MetricsTimer
    )
    METRICS_ENABLED = True
except ImportError:
    print("⚠️  Warning: metrics module not found. Metrics will not be recorded.")
    METRICS_ENABLED = False

# --- CONFIGURATION ---
NATS_URI = "nats://localhost:4222"
FEEDBACK_TOPIC = "feedback.carLoan"
MODEL_PATH = os.path.join(PARENT_DIR, "Persistence", "model_car.json")
LOG_ENABLED = True  # Set to False to disable logging

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))
LOG_FILE = os.path.join(CURRENT_DIR, "feedback_node.log")
METRICS_PORT = 8006  # Dedicated port for feedback metrics

NUM_FEATURES = CONFIG["gmm_num_features"]
CAT_FEATURES = CONFIG["gmm_cat_features"]

# Batch processing config
FEEDBACK_BATCH_SIZE = 20
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
        self.tp_count = 0
        self.fp_count = 0
        self.tn_count = 0
        self.fn_count = 0
        self.last_save_time = time.time()
        self.lock = threading.Lock()
        
        # Load initial state
        self.load_model()
        self.load_masterfile()
        
        # Start background metrics updater
        if METRICS_ENABLED:
            self._start_metrics_updater()
    
    def load_model(self):
        """Load model from disk"""
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
        
        log_message(f"Loading model from {MODEL_PATH}...")
        self.model, self.scaler, self.encoder = load_model_system(MODEL_PATH)
        
        # 🔑 Log buffer restoration
        buffer_size = len(self.model.fn_buffer_num)
        log_message(f"✓ Model loaded. Components: {self.model.n_components}")
        if buffer_size > 0:
            log_message(f"  └─ FN Buffer restored: {buffer_size} samples")
        
        # 📊 METRIC: Update model components
        if METRICS_ENABLED:
            update_model_components(self.model.n_components)
            log_message(f"📊 Metric recorded: Model components = {self.model.n_components}")
    
    def load_masterfile(self):
        """Load MASTERFILE from Redis"""
        import redis
        import pickle
        
        log_message(f"Loading MASTERFILE from Redis @ {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})...")
        
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=False
            )
            redis_client.ping()
            
            serialized = redis_client.get('masterfile:data')
            if serialized is None:
                raise RuntimeError("MASTERFILE not found in Redis. Run load_csvs_to_redis.py first.")
            
            self.masterfile_df = pickle.loads(serialized)
            self.masterfile_df.set_index('customer_id', inplace=True)
            log_message(f"✓ MASTERFILE loaded from Redis. {len(self.masterfile_df)} customers indexed.")
            
        except redis.ConnectionError as e:
            raise RuntimeError(f"Redis connection failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading MASTERFILE from Redis: {e}")
    
    def save_model(self):
        """Save model to disk"""
        log_message(f"\n💾 Saving model after {self.update_count} updates...")
        
        save_start_time = time.time()
        
        try:
            # 🔑 FLUSH BUFFER BEFORE SAVING
            self.model.flush_buffer()
            
            save_model_system(self.model, self.scaler, self.encoder, MODEL_PATH)
            save_duration = time.time() - save_start_time
            self.last_save_time = time.time()
            
            log_message(f"✓ Model saved to {MODEL_PATH} in {save_duration:.3f}s")
            log_message(f"✓ Current state: Components={self.model.n_components}, TP={self.tp_count}, FP={self.fp_count}, FN={self.fn_count}, TN={self.tn_count}\n")
            
            # 📊 METRIC: Record save time
            if METRICS_ENABLED:
                record_save_time(save_duration, success=True)
                update_model_components(self.model.n_components)
                log_message(f"📊 Metric recorded: Save time = {save_duration:.3f}s, Components = {self.model.n_components}")
                
        except Exception as e:
            save_duration = time.time() - save_start_time
            log_message(f"❌ Failed to save model: {e}")
            
            # 📊 METRIC: Record failed save
            if METRICS_ENABLED:
                record_save_time(save_duration, success=False)
                record_feedback_error('save_failed')
    
    def parse_feedback_string(self, feedback_str):
        """
        Parse feedback string in format: 'custID | feedback_type'
        Returns: (customer_id, feedback_type) or (None, None) if invalid
        """
        try:
            parts = feedback_str.split('|')
            if len(parts) != 2:
                log_message(f"⚠ Invalid format: '{feedback_str}'. Expected 'custID | feedback_type'")
                return None, None
            
            customer_id = parts[0].strip()
            feedback_type = parts[1].strip().upper()
            
            if feedback_type not in ['TP', 'FP', 'TN', 'FN']:
                log_message(f"⚠ Invalid feedback type: '{feedback_type}'. Must be TP, FP, TN, or FN")
                return None, None
            
            return customer_id, feedback_type
        except Exception as e:
            log_message(f"⚠ Error parsing feedback string '{feedback_str}': {e}")
            return None, None
    
    def process_feedback(self, feedback_str):
        """Add feedback to buffer and process if batch is full"""
        customer_id, feedback_type = self.parse_feedback_string(feedback_str)
        
        if customer_id is None or feedback_type is None:
            if METRICS_ENABLED:
                record_feedback_error('invalid_format')
            return f"error_invalid_format"
        
        log_message(f"📥 RECEIVED FEEDBACK | Customer: {customer_id} | Type: {feedback_type}")
        
        # 📊 METRIC: Record feedback received
        if METRICS_ENABLED:
            # Map feedback types to boolean for metrics (TP/FN are positive, FP/TN are negative)
            is_positive = feedback_type in ['TP', 'FN']
            record_feedback(is_positive)
        
        with self.lock:
            self.feedback_buffer.append({
                'customer_id': customer_id,
                'feedback_type': feedback_type
            })
            
            # 📊 METRIC: Update buffer size
            if METRICS_ENABLED:
                update_feedback_buffer_size(len(self.feedback_buffer))
            
            log_message(f"Buffer size: {len(self.feedback_buffer)}/{FEEDBACK_BATCH_SIZE}")
            
            # Check if we should process the batch
            should_process = (
                len(self.feedback_buffer) >= FEEDBACK_BATCH_SIZE or
                (time.time() - self.last_save_time) >= AUTO_SAVE_INTERVAL
            )
            
            if should_process:
                self._process_batch()
        
        # Return a simple string for tracking
        return f"processed_{customer_id}_{feedback_type}"
    
    def _process_batch(self):
        """Process all feedback in buffer and update model"""
        if len(self.feedback_buffer) == 0:
            return
        
        log_message(f"\n{'='*60}")
        log_message(f"🔄 Processing batch of {len(self.feedback_buffer)} feedback points")
        log_message(f"{'='*60}")
        
        batch_data = list(self.feedback_buffer)
        self.feedback_buffer.clear()
        
        # 📊 METRIC: Clear buffer size
        if METRICS_ENABLED:
            update_feedback_buffer_size(0)
            record_batch_update()
        
        success_count = 0
        error_count = 0
        
        for feedback in batch_data:
            customer_id = feedback['customer_id']
            feedback_type = feedback['feedback_type']
            
            update_start_time = time.time()
            
            try:
                # Look up customer features from MASTERFILE
                if customer_id not in self.masterfile_df.index:
                    log_message(f"⚠ ERROR | Customer {customer_id} not found in MASTERFILE. Skipping.")
                    error_count += 1
                    
                    # 📊 METRIC: Record error
                    if METRICS_ENABLED:
                        record_feedback_error('customer_not_found')
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
                is_in, k, score, all_m, exemplars = result_tuple
                
                # Map feedback type to model update parameters
                # TP: is_in=True, bought=True
                # FP: is_in=True, bought=False
                # FN: is_in=False, bought=True
                # TN: is_in=False, bought=False
                
                if feedback_type == 'TP':
                    is_in_actual = True
                    bought_actual = True
                    self.tp_count += 1
                    icon = "✓✓"
                elif feedback_type == 'FP':
                    is_in_actual = True
                    bought_actual = False
                    self.fp_count += 1
                    icon = "✓✗"
                elif feedback_type == 'FN':
                    is_in_actual = False
                    bought_actual = True
                    self.fn_count += 1
                    icon = "✗✓"
                else:  # TN
                    is_in_actual = False
                    bought_actual = False
                    self.tn_count += 1
                    icon = "✗✗"
                
                # Update model with feedback
                # Note: We use the actual prediction result (is_in, k, score, all_m, exemplars)
                # but interpret feedback_type to determine bought_actual
                self.model.update(x_num, x_cat, bought_actual, result_tuple, meta=customer_id)
                
                # 📊 METRIC: Record update time
                update_duration = time.time() - update_start_time
                if METRICS_ENABLED:
                    record_update_time(update_duration)
                
                self.update_count += 1
                success_count += 1
                
                log_message(f"{icon} {feedback_type} | Customer: {customer_id} | Cluster: {k} | Score: {score:.2f} | "
                          f"Predicted: {'IN' if is_in else 'OUT'} | Update #{self.update_count} | Latency: {update_duration*1000:.2f}ms")
                
            except Exception as e:
                log_message(f"⚠ ERROR | Failed to process feedback for {customer_id}: {e}")
                error_count += 1
                
                # 📊 METRIC: Record error
                if METRICS_ENABLED:
                    error_type = type(e).__name__
                    record_feedback_error(error_type)
        
        # Save updated model
        if success_count > 0:
            self.save_model()
            log_message(f"✓ Batch complete: {success_count} updates, {error_count} errors")
        else:
            log_message(f"⚠ Batch failed: No successful updates")
    
    def _start_metrics_updater(self):
        """Background thread to update time-based metrics"""
        def updater():
            while True:
                time.sleep(5)  # Update every 5 seconds
                try:
                    # Update time since last save
                    time_since_save = time.time() - self.last_save_time
                    update_time_since_save(time_since_save)
                    
                    # Update memory usage
                    try:
                        import psutil
                        process = psutil.Process()
                        memory_bytes = process.memory_info().rss
                        update_memory_usage('ml_feedback', memory_bytes)
                    except ImportError:
                        pass
                except Exception as e:
                    log_message(f"⚠️  Metrics updater error: {e}")
        
        thread = threading.Thread(target=updater, daemon=True)
        thread.start()
        log_message("✓ Background metrics updater started")

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
    log_message(f"Metrics:        {'ENABLED on port ' + str(METRICS_PORT) if METRICS_ENABLED else 'DISABLED'}")
    log_message(f"Batch Config:   Update every {FEEDBACK_BATCH_SIZE} feedbacks")
    log_message(f"Auto-save:      Every {AUTO_SAVE_INTERVAL} seconds")
    log_message(f"Input Format:   'custID | feedback_type' (TP/FP/TN/FN)")
    log_message(f"Buffer Flush:   ENABLED (flushes before save)")
    log_message("═══════════════════════════════════════════════\n")
    
    # 📊 Initialize metrics server
    if METRICS_ENABLED:
        try:
            metrics_manager = initialize_metrics("ml_car_feedback", port=METRICS_PORT)
            log_message(f"✓ Metrics server initialized on port {METRICS_PORT}")
        except Exception as e:
            log_message(f"⚠️  Failed to initialize metrics: {e}")
    
    # Expected schema: feedback_string (str) in format "custID | feedback_type"
    class FeedbackSchema(pw.Schema):
        feedback_string: str
    
    # 1. Read feedback from NATS
    feedback_stream = pw.io.nats.read(
        uri=NATS_URI,
        topic=FEEDBACK_TOPIC,
        format="json",
        schema=FeedbackSchema
    )
    
    log_message(f"✓ Listening for feedback on '{FEEDBACK_TOPIC}'...")
    log_message(f"✓ Expected format: {{\"feedback_string\": \"custID | TP/FP/TN/FN\"}}\n")
    
    # 2. Process each feedback point
    processed = feedback_stream.select(
        feedback_string=pw.this.feedback_string,
        status=pw.apply_with_type(
            lambda fs: processor.process_feedback(fs),
            str,
            pw.this.feedback_string
        )
    )
    
    pw.io.null.write(processed)
    
    log_message("✓ Car Loan Feedback Node is running.\n")
    
    # Periodically update component uptime
    if METRICS_ENABLED:
        def update_uptime():
            while True:
                time.sleep(30)
                try:
                    metrics_manager.update_component_uptime()
                except:
                    pass
        
        uptime_thread = threading.Thread(target=update_uptime, daemon=True)
        uptime_thread.start()
    
    pw.run()

if __name__ == "__main__":
    run_feedback_node()