# tester.py
# Location: ./TargettedCalling/carLoanPredictor/tester.py
# Purpose: Listen to leads.callCarLoan, simulate customer decisions, stream to feedback.carLoan

import pathway as pw
import numpy as np
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
NATS_URI = "nats://localhost:4222"
INPUT_TOPIC = "leads.callCarLoan"
OUTPUT_TOPIC = "feedback.carLoan"
LOG_ENABLED = True  # Set to False to disable logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "tester.log")

# Simulation parameters
BASE_PURCHASE_PROBABILITY = 0.7  # Base 30% chance customer buys
PREDICTION_BONUS = 0.15  # +15% if model predicted YES

# Schema for all predictions (both qualified and rejected)
class PredictionSchema(pw.Schema):
    customer_id: str
    predicted_eligible: bool
    cluster_id: int
    confidence_score: float
    similar_customers: str  # JSON string of exemplar IDs

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

class FeedbackSimulator:
    """Simulates customer feedback for testing"""
    
    def __init__(self):
        self.total_processed = 0
        self.model_yes_bought = 0
        self.model_yes_rejected = 0
        self.model_no_bought = 0
        self.model_no_rejected = 0
        np.random.seed()  # Ensure randomness
    
    def simulate_customer_decision(self, customer_id: str, predicted_eligible: bool,
                                   confidence_score: float, cluster_id: int, 
                                   similar_customers: str):
        """
        Simulate whether a customer buys the loan or not.
        Model predictions influence but don't determine the outcome.
        """
        self.total_processed += 1
        
        # Parse similar customers
        try:
            similar_list = json.loads(similar_customers)
        except:
            similar_list = []
        
        # Simulate decision - model prediction increases likelihood
        if predicted_eligible:
            # Model said YES - higher chance they actually buy
            adjusted_probability = BASE_PURCHASE_PROBABILITY + PREDICTION_BONUS
        else:
            # Model said NO - use base probability
            adjusted_probability = BASE_PURCHASE_PROBABILITY
        
        # Add small bonus for higher confidence scores (only if positive score)
        if confidence_score > -100:
            confidence_bonus = min(confidence_score / 1000.0, 0.1)  # Max +10%
            adjusted_probability += confidence_bonus
        
        # Cap at 90%
        adjusted_probability = min(adjusted_probability, 0.9)
        
        # Make the decision
        actually_bought = bool(np.random.random() < adjusted_probability)
        
        # Track statistics (True Positives, False Positives, etc.)
        if predicted_eligible and actually_bought:
            self.model_yes_bought += 1
            outcome = "✓✓ TRUE POSITIVE"
        elif predicted_eligible and not actually_bought:
            self.model_yes_rejected += 1
            outcome = "✓✗ FALSE POSITIVE"
        elif not predicted_eligible and actually_bought:
            self.model_no_bought += 1
            outcome = "✗✓ FALSE NEGATIVE"
        else:  # not predicted_eligible and not actually_bought
            self.model_no_rejected += 1
            outcome = "✗✗ TRUE NEGATIVE"
        
        # Format similar customers for logging
        similar_str = f"{len(similar_list)} similar: {similar_list[:3]}" if similar_list else "no similar"
        
        # Calculate accuracy metrics
        tp = self.model_yes_bought
        fp = self.model_yes_rejected
        fn = self.model_no_bought
        tn = self.model_no_rejected
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        accuracy = (tp + tn) / self.total_processed if self.total_processed > 0 else 0
        
        # Log the simulation
        log_message(f"{outcome} | Customer: {customer_id} | Cluster: {cluster_id} | "
                   f"Score: {confidence_score:.2f} | {similar_str} | "
                   f"Prob: {adjusted_probability:.2f} | "
                   f"Total: {self.total_processed} | Acc: {accuracy:.2%} | Prec: {precision:.2%} | Rec: {recall:.2%}")
        
        # Return as pipe-delimited string
        return f"{customer_id}|{int(actually_bought)}"

# Global simulator instance
simulator = FeedbackSimulator()

def run_tester():
    log_message("═══════════════════════════════════════════════")
    log_message("       CAR LOAN TESTER NODE (PATHWAY)         ")
    log_message("═══════════════════════════════════════════════")
    log_message(f"Input Topic:    {INPUT_TOPIC}")
    log_message(f"Output Topic:   {OUTPUT_TOPIC}")
    log_message(f"Log File:       {LOG_FILE if LOG_ENABLED else 'DISABLED'}")
    log_message(f"Base Purchase:  {BASE_PURCHASE_PROBABILITY * 100:.1f}%")
    log_message(f"Prediction Bonus: +{PREDICTION_BONUS * 100:.1f}%")
    log_message("═══════════════════════════════════════════════\n")
    
    # 1. Read ALL predictions from prediction node
    all_predictions = pw.io.nats.read(
        uri=NATS_URI,
        topic=INPUT_TOPIC,
        format="json",
        schema=PredictionSchema
    )
    
    log_message(f"✓ LISTENING TO: {INPUT_TOPIC}")
    log_message(f"✓ Listening for ALL car loan predictions (qualified + rejected)...")
    
    # 2. Simulate customer decisions - returns pipe-delimited string
    with_decision = all_predictions.select(
        decision_str=pw.apply_with_type(
            lambda cid, pred, score, cluster, similar: simulator.simulate_customer_decision(
                cid, pred, score, cluster, similar
            ),
            str,
            pw.this.customer_id,
            pw.this.predicted_eligible,
            pw.this.confidence_score,
            pw.this.cluster_id,
            pw.this.similar_customers
        )
    )
    
    # 3. Parse the decision string
    feedback_data = with_decision.select(
        customer_id=pw.apply_with_type(
            lambda s: s.split('|')[0],
            str,
            pw.this.decision_str
        ),
        custBoughtLoanOrNot=pw.apply_with_type(
            lambda s: bool(int(s.split('|')[1])),
            bool,
            pw.this.decision_str
        )
    )
    
    log_message(f"✓ STREAMING TO: {OUTPUT_TOPIC}")
    log_message(f"✓ Streaming simulated feedback to '{OUTPUT_TOPIC}'...")
    
    # 4. Write feedback to NATS
    pw.io.nats.write(
        feedback_data,
        uri=NATS_URI,
        topic=OUTPUT_TOPIC,
        format="json"
    )
    
    log_message("\n✓ Tester Node is running.\n")
    log_message("=" * 60)
    log_message("SIMULATION FLOW:")
    log_message(f"  1. Listen to ALL predictions on: {INPUT_TOPIC}")
    log_message(f"  2. Simulate customer decision (model influences odds)")
    log_message(f"  3. Stream actual outcome to: {OUTPUT_TOPIC}")
    log_message(f"  4. Track: TP, FP, FN, TN, Accuracy, Precision, Recall")
    log_message("=" * 60 + "\n")
    
    pw.run()

if __name__ == "__main__":
    run_tester()