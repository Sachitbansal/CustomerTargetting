"""
Oracle Rules-Based Predictor Node - SCHEMA ALIGNED
Reads from leads.callCarLoan, uses rules-based logic to make predictions, 
outputs feedback classifications (TP/FP/TN/FN) to feedback.carLoan
Location: ./TargettedCalling/oracle/oracle_predictor.py
"""

import pathway as pw
import pandas as pd
import numpy as np
import os
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---
NATS_URI = "nats://localhost:4222"
INPUT_TOPIC = "leads.callCarLoan"  # Reads GMM predictions
OUTPUT_TOPIC = "feedback.carLoan"  # Writes feedback for GMM training
LOG_ENABLED = True
LOG_FILE = Path(__file__).parent / "oracle_predictor.log"

# Redis configuration
import os
import sys
ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))

TARGET_VARIABLE = "opted_car_loan"  # Can be: opted_car_loan, opted_home_loan, recommend_nifty50, recommend_elss

# Feature configuration (kept for compatibility)
NUMERICAL_FEATURES = [
    'age', 'dependents_count', 'yearly_income', 'account_age_months',
    'initial_credit_score', 'existing_loans_count', 'existing_loan_monthly_EMI_total',
    'total_credit_limit', 'initial_credit_utilization_ratio', 'initial_avg_monthly_balance',
    'initial_savings_rate', 'txn_count_last_30d', 'high_value_txn_count_30d',
    'bounced_txn_count', 'final_avg_monthly_balance', 'monthly_fuel_spend',
    'monthly_transport_service_spend', 'avg_monthly_investment_debit', 'final_credit_score',
    'dti_ratio', 'savings_rate', 'income_to_limit', 'txn_intensity',
    'age_x_dependents', 'score_x_log_income'
]

CATEGORICAL_FEATURES = [
    'gender', 'marital_status', 'employment_type', 'occupation',
    'education_level', 'city_tier', 'has_existing_auto_loan',
    'has_existing_investment_account'
]

# ✅ SCHEMA MUST MATCH car_loan_prediction_node.py OUTPUT
class GMMPredictionSchema(pw.Schema):
    customer_id: str
    predicted_eligible: bool
    cluster_id: int
    confidence_score: float
    similar_customers: str  # JSON array of exemplar customer IDs

# ✅ OUTPUT SCHEMA MUST MATCH car_loan_feedback_node.py INPUT
class FeedbackOutputSchema(pw.Schema):
    feedback_string: str  # Format: "custID | TP/FP/TN/FN"


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


class RulesBasedOracle:
    """
    Rules-based predictor that replicates the exact logic from generate_data.py
    for each target variable
    """
    
    def __init__(self):
        self.masterfile_df = None
        self.total_processed = 0
        self.tp_count = 0
        self.fp_count = 0
        self.tn_count = 0
        self.fn_count = 0
        
        self._load_masterfile()
    
    def _load_masterfile(self):
        """Load masterfile from Redis"""
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
                log_message("❌ MASTERFILE not found in Redis. Run load_csvs_to_redis.py first.")
                return
            
            self.masterfile_df = pickle.loads(serialized)
            self.masterfile_df.set_index('customer_id', inplace=True)
            log_message(f"✓ MASTERFILE loaded from Redis: {len(self.masterfile_df)} customers\n")
            
        except redis.ConnectionError as e:
            log_message(f"❌ Redis connection failed: {e}")
        except Exception as e:
            log_message(f"❌ Error loading MASTERFILE from Redis: {e}")
    
    def _predict_home_loan(self, customer_data):
        """
        Replicates home loan target logic from generate_data.py:
        score_hl = (yearly_income > 1_200_000)*2 + (city_tier == 'tier1') + 
                   (final_credit_score > 750)*3 - (dti_ratio > 0.4)*2 - (bounced_txn_count > 0)*4
        prob_hl = 1 / (1 + exp(-score_hl))
        """
        score = 0
        
        # Positive factors
        if customer_data.get('yearly_income', 0) > 1_200_000:
            score += 2
        if customer_data.get('city_tier', '') == 'tier1':
            score += 1
        if customer_data.get('final_credit_score', 0) > 750:
            score += 3
        
        # Negative factors
        if customer_data.get('dti_ratio', 0) > 0.4:
            score -= 2
        if customer_data.get('bounced_txn_count', 0) > 0:
            score -= 4
        
        # Sigmoid probability
        prob = 1 / (1 + np.exp(-score))
        
        # Dampen if not interested (using initial conditions as proxy)
        if customer_data.get('initial_credit_score', 0) <= 680 or \
           customer_data.get('yearly_income', 0) <= 800_000 or \
           customer_data.get('dti_ratio', 0) >= 0.5:
            prob *= 0.3
        
        return prob > 0.5, prob
    
    def _predict_car_loan(self, customer_data):
        """
        Replicates car loan target logic from generate_data.py:
        score_cl = (yearly_income > 900_000)*2 + (final_credit_score > 720)*3 + 
                   (monthly_transport_service_spend > 3000)*3 - (has_existing_auto_loan == 1)*5 - 
                   (dti_ratio > 0.45)*2
        prob_cl = 1 / (1 + exp(-score_cl))
        """
        score = 0
        
        # Positive factors
        if customer_data.get('yearly_income', 0) > 900_000:
            score += 2
        if customer_data.get('final_credit_score', 0) > 720:
            score += 3
        if customer_data.get('monthly_transport_service_spend', 0) > 3000:
            score += 3
        
        # Negative factors
        if customer_data.get('has_existing_auto_loan', 0) == 1:
            score -= 5
        if customer_data.get('dti_ratio', 0) > 0.45:
            score -= 2
        
        # Sigmoid probability
        prob = 1 / (1 + np.exp(-score))
        
        return prob > 0.5, prob
    
    def _predict_nifty50(self, customer_data):
        """
        Replicates Nifty 50 recommendation logic from generate_data.py:
        condition = (yearly_income > 700_000) & (final_credit_score > 700) & 
                    (age < 45) & (has_existing_investment_account == 0)
        """
        condition = (
            customer_data.get('yearly_income', 0) > 700_000 and
            customer_data.get('final_credit_score', 0) > 700 and
            customer_data.get('age', 100) < 45 and
            customer_data.get('has_existing_investment_account', 1) == 0
        )
        
        # Binary decision with high confidence if condition met
        prob = 0.95 if condition else 0.05
        return condition, prob
    
    def _predict_elss(self, customer_data):
        """
        Replicates ELSS recommendation logic from generate_data.py:
        condition = (employment_type == 'Salaried') & (yearly_income > 800_000) & 
                    (avg_monthly_investment_debit < yearly_income/12 * 0.1)
        """
        monthly_income = customer_data.get('yearly_income', 0) / 12
        investment_threshold = monthly_income * 0.1
        
        condition = (
            customer_data.get('employment_type', '') == 'Salaried' and
            customer_data.get('yearly_income', 0) > 800_000 and
            customer_data.get('avg_monthly_investment_debit', float('inf')) < investment_threshold
        )
        
        # Binary decision with high confidence if condition met
        prob = 0.95 if condition else 0.05
        return condition, prob
    
    def predict_ground_truth(self, customer_id: str):
        """
        Predict ground truth based on TARGET_VARIABLE using rules-based logic
        Returns: (oracle_bought: bool, probability: float)
        """
        if customer_id not in self.masterfile_df.index:
            log_message(f"⚠️  WARNING: Customer {customer_id} not found in MASTERFILE")
            return False, 0.5
        
        customer_data = self.masterfile_df.loc[customer_id].to_dict()
        
        # Route to appropriate prediction function based on target variable
        if TARGET_VARIABLE == "opted_home_loan":
            return self._predict_home_loan(customer_data)
        elif TARGET_VARIABLE == "opted_car_loan":
            return self._predict_car_loan(customer_data)
        elif TARGET_VARIABLE == "recommend_nifty50":
            return self._predict_nifty50(customer_data)
        elif TARGET_VARIABLE == "recommend_elss":
            return self._predict_elss(customer_data)
        else:
            log_message(f"❌ ERROR: Unknown target variable '{TARGET_VARIABLE}'")
            return False, 0.5
    
    def predict_and_classify(self, customer_id: str, gmm_predicted_eligible: bool, 
                            cluster_id: int, confidence_score: float, 
                            similar_customers: str):
        """
        Make Oracle prediction using rules and classify feedback type.
        Returns feedback_string in format: "custID | TP/FP/TN/FN"
        
        ✅ CRITICAL ALIGNMENT:
        - Input parameter names MUST match GMMPredictionSchema field names
        - predicted_eligible (from GMM) = is_in (GMM says customer qualifies)
        - oracle_bought (from Rules) = ground truth (customer actually bought)
        
        Classification logic:
        - TP: GMM says YES (predicted_eligible=True), Oracle says YES (bought=True)
        - FP: GMM says YES (predicted_eligible=True), Oracle says NO (bought=False)
        - FN: GMM says NO (predicted_eligible=False), Oracle says YES (bought=True)
        - TN: GMM says NO (predicted_eligible=False), Oracle says NO (bought=False)
        """
        self.total_processed += 1
        
        # Get ground truth prediction using rules-based logic
        oracle_bought, probability = self.predict_ground_truth(customer_id)
        
        # Classify feedback type: GMM prediction vs Oracle ground truth
        if gmm_predicted_eligible and oracle_bought:
            feedback_type = "TP"
            self.tp_count += 1
            icon = "✓✓"
            status = "CORRECT"
        elif gmm_predicted_eligible and not oracle_bought:
            feedback_type = "FP"
            self.fp_count += 1
            icon = "✓✗"
            status = "FALSE ALARM"
        elif not gmm_predicted_eligible and oracle_bought:
            feedback_type = "FN"
            self.fn_count += 1
            icon = "✗✓"
            status = "MISSED"
        else:  # not gmm_predicted_eligible and not oracle_bought
            feedback_type = "TN"
            self.tn_count += 1
            icon = "✗✗"
            status = "CORRECT"
        
        # Parse similar customers for logging
        try:
            import json
            similar_list = json.loads(similar_customers)
            similar_count = len(similar_list)
            similar_str = f"{similar_count} similar"
        except:
            similar_str = "no similar"
        
        # Calculate running metrics
        accuracy = (self.tp_count + self.tn_count) / self.total_processed * 100
        
        if self.tp_count + self.fp_count > 0:
            precision = self.tp_count / (self.tp_count + self.fp_count) * 100
        else:
            precision = 0.0
        
        if self.tp_count + self.fn_count > 0:
            recall = self.tp_count / (self.tp_count + self.fn_count) * 100
        else:
            recall = 0.0
        
        # Log detailed prediction with full confusion matrix
        log_message(
            f"{icon} {feedback_type:2s} {status:12s} | "
            f"GMM: {'YES' if gmm_predicted_eligible else 'NO ':3s} → "
            f"Oracle: {'YES' if oracle_bought else 'NO':3s} ({probability:.1%}) | "
            f"Cust: {customer_id:10s} | Cluster: {cluster_id:2d} | "
            f"GMM Score: {confidence_score:5.2f} | {similar_str:12s} | "
            f"Count: {self.total_processed:4d} | "
            f"TP:{self.tp_count:3d} FP:{self.fp_count:3d} FN:{self.fn_count:3d} TN:{self.tn_count:3d} | "
            f"Acc:{accuracy:5.1f}% Prec:{precision:5.1f}% Rec:{recall:5.1f}%"
        )
        
        # ✅ Return feedback string in EXACT format expected by feedback_node
        feedback_string = f"{customer_id} | {feedback_type}"
        return feedback_string


# Global predictor instance
predictor = RulesBasedOracle()


def run_oracle_predictor():
    log_message("\n" + "="*70)
    log_message("  ORACLE RULES-BASED PREDICTOR NODE - SCHEMA ALIGNED  ")
    log_message("="*70)
    log_message(f"Input Topic:     {INPUT_TOPIC}")
    log_message(f"Output Topic:    {OUTPUT_TOPIC}")
    log_message(f"Output Format:   feedback_string = 'custID | TP/FP/TN/FN'")
    log_message(f"Target Variable: {TARGET_VARIABLE}")
    log_message(f"Prediction Mode: RULES-BASED (Fast, No NN)")
    log_message(f"Log File:        {LOG_FILE if LOG_ENABLED else 'DISABLED'}")
    log_message("="*70)
    log_message("RULES-BASED LOGIC:")
    
    if TARGET_VARIABLE == "opted_car_loan":
        log_message("  Car Loan: income>900K + score>720 + transport>3K - auto_loan - high_dti")
    elif TARGET_VARIABLE == "opted_home_loan":
        log_message("  Home Loan: income>1.2M + tier1 + score>750 - high_dti - bounced")
    elif TARGET_VARIABLE == "recommend_nifty50":
        log_message("  Nifty50: income>700K + score>700 + age<45 + no_investment")
    elif TARGET_VARIABLE == "recommend_elss":
        log_message("  ELSS: salaried + income>800K + low_investment")
    
    log_message("="*70)
    log_message("SCHEMA VALIDATION:")
    log_message(f"  INPUT (from GMM):  customer_id, predicted_eligible, cluster_id,")
    log_message(f"                     confidence_score, similar_customers")
    log_message(f"  OUTPUT (to Feedback): feedback_string")
    log_message("="*70 + "\n")
    
    # ✅ 1. Read GMM predictions with EXACT schema from car_loan_prediction_node.py
    gmm_predictions = pw.io.nats.read(
        uri=NATS_URI,
        topic=INPUT_TOPIC,
        format="json",
        schema=GMMPredictionSchema
    )
    
    log_message(f"✓ LISTENING TO: {INPUT_TOPIC}")
    log_message(f"✓ Waiting for GMM predictions...")
    
    # ✅ 2. Generate feedback classifications (TP/FP/TN/FN)
    # Parameter names MUST match schema field names exactly
    feedback_output = gmm_predictions.select(
        feedback_string=pw.apply_with_type(
            lambda cid, pred_eligible, cluster, score, similar: predictor.predict_and_classify(
                cid, pred_eligible, cluster, score, similar
            ),
            str,
            pw.this.customer_id,
            pw.this.predicted_eligible,  # ✅ Matches schema field name
            pw.this.cluster_id,           # ✅ Matches schema field name
            pw.this.confidence_score,     # ✅ Matches schema field name
            pw.this.similar_customers     # ✅ Matches schema field name
        )
    )
    
    log_message(f"✓ STREAMING TO: {OUTPUT_TOPIC}")
    log_message(f"✓ Output format: {{\"feedback_string\": \"custID | TP/FP/TN/FN\"}}")
    
    # ✅ 3. Write feedback to NATS in correct format for feedback_node
    pw.io.nats.write(
        feedback_output,
        uri=NATS_URI,
        topic=OUTPUT_TOPIC,
        format="json"
    )
    
    log_message("\n✓ Oracle Predictor Node is running.\n")
    log_message("=" * 70)
    log_message("COMPLETE DATA FLOW:")
    log_message("=" * 70)
    log_message("  [MASTERFILE.csv]")
    log_message("        ↓")
    log_message("  [leads.checkCarLoan] ← Customer data")
    log_message("        ↓")
    log_message("  [GMM Predictor] → car_loan_prediction_node.py")
    log_message("        ↓ predicted_eligible, cluster_id, confidence_score, similar_customers")
    log_message(f"  [{INPUT_TOPIC}]")
    log_message("        ↓")
    log_message("  [Rules-Based Oracle] ← THIS NODE")
    log_message("        ↓ Compare GMM vs Rules ground truth")
    log_message("        ↓ Classify: TP/FP/TN/FN")
    log_message(f"  [{OUTPUT_TOPIC}] ← feedback_string = 'custID | TP/FP/TN/FN'")
    log_message("        ↓")
    log_message("  [Feedback Node] → car_loan_feedback_node.py")
    log_message("        ↓ Batch process feedback")
    log_message("        ↓ Update GMM clusters")
    log_message("  [model_car.json] ← Updated model")
    log_message("=" * 70)
    log_message("\nFEEDBACK CLASSIFICATION:")
    log_message("  TP (✓✓): GMM=YES, Oracle=YES → Reinforce cluster")
    log_message("  FP (✓✗): GMM=YES, Oracle=NO  → Penalize false positive")
    log_message("  FN (✗✓): GMM=NO,  Oracle=YES → Learn missed opportunity")
    log_message("  TN (✗✗): GMM=NO,  Oracle=NO  → Confirm rejection")
    log_message("=" * 70 + "\n")
    
    pw.run()


if __name__ == "__main__":
    run_oracle_predictor()