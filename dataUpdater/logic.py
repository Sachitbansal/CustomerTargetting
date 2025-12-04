# MASTERFILENode/logic.py (Fixed - Complete Columns)
import pathway as pw
import numpy as np

# Define UDFs with proper type annotations to avoid ANY type issues
@pw.udf
def decay_func(n: int) -> float:
    """Calculate decay factor as 0.98^n"""
    return 0.98 ** float(n)

@pw.udf
def log1p_func(x: float) -> float:
    """Calculate log(1 + x) safely"""
    return float(np.log1p(x))

def calculate_new_state(joined_data):
    """
    Takes a table that results from joining Master Data + Transaction Aggregations.
    Returns a dictionary of Column Expressions for the .select() method.
    
    IMPORTANT: This must return ALL columns needed by the dispatcher node.
    
    Note: This join only includes customers who had transactions in this batch,
    which is appropriate since we're only enriching on new transaction events.
    """
    
    # --- LOGIC START ---
    
    # 1. Update Balance
    current_balance = joined_data.final_avg_monthly_balance + joined_data.total_amount_change
    
    # 2. Credit Score Logic
    score_penalty = joined_data.bounced_count_change * 10
    score_reward = joined_data.successful_debits_count * 0.5
    new_credit_score = joined_data.final_credit_score - score_penalty + score_reward

    # 3. Decay Logic (0.98 ^ num_new_txns)
    decay_factor = decay_func(joined_data.num_new_txns)

    # Log income
    log_income = log1p_func(joined_data.yearly_income)

    # Pre-compute decayed values
    decayed_txn_count = (joined_data.txn_count_last_30d * decay_factor) + joined_data.num_new_txns
    decayed_fuel_spend = (joined_data.monthly_fuel_spend * decay_factor) + joined_data.fuel_spend_change
    decayed_transport_spend = (joined_data.monthly_transport_service_spend * decay_factor) + joined_data.transport_spend_change
    decayed_investment_debit = (joined_data.avg_monthly_investment_debit * decay_factor) + joined_data.investment_debit_change

    # 4. Return Dictionary for .select() - COMPLETE COLUMN SET
    return {
        # --- CRITICAL: ID & Timestamp (Required by dispatcher) ---
        "customer_id": joined_data.customer_id,
        "last_update_timestamp": joined_data.max_txn_time,
        
        # --- Static/Semi-Static Features ---
        "age": joined_data.age,
        "gender": joined_data.gender,
        "marital_status": joined_data.marital_status,
        "dependents_count": joined_data.dependents_count,
        "employment_type": joined_data.employment_type,
        "occupation": joined_data.occupation,
        "education_level": joined_data.education_level,
        "city_tier": joined_data.city_tier,
        "yearly_income": joined_data.yearly_income,
        "account_age_months": joined_data.account_age_months,
        "initial_credit_score": joined_data.initial_credit_score,
        "existing_loans_count": joined_data.existing_loans_count,
        "existing_loan_monthly_EMI_total": joined_data.existing_loan_monthly_EMI_total,
        "total_credit_limit": joined_data.total_credit_limit,
        "initial_credit_utilization_ratio": joined_data.initial_credit_utilization_ratio,
        "initial_avg_monthly_balance": joined_data.initial_avg_monthly_balance,
        "initial_savings_rate": joined_data.initial_savings_rate,
        "has_existing_auto_loan": joined_data.has_existing_auto_loan,
        "has_existing_investment_account": joined_data.has_existing_investment_account,

        # --- Updated Aggregated Features ---
        "txn_count_last_30d": decayed_txn_count,
        "high_value_txn_count_30d": joined_data.high_value_txn_count_30d,
        "bounced_txn_count": joined_data.bounced_txn_count + joined_data.bounced_count_change,
        "final_avg_monthly_balance": current_balance,
        "monthly_fuel_spend": decayed_fuel_spend,
        "monthly_transport_service_spend": decayed_transport_spend,
        "avg_monthly_investment_debit": decayed_investment_debit,
        "final_credit_score": new_credit_score,

        # --- Updated Ratio/Interaction Features ---
        "dti_ratio": joined_data.dti_ratio,
        "savings_rate": current_balance / ((joined_data.yearly_income / 12) + 1),
        "income_to_limit": joined_data.income_to_limit,
        "txn_intensity": decayed_txn_count / ((joined_data.yearly_income / 10000) + 1),
        "age_x_dependents": joined_data.age_x_dependents,
        "score_x_log_income": new_credit_score * log_income,

        # --- CRITICAL: Target Columns (Required by dispatcher) ---
        "opted_home_loan": joined_data.opted_home_loan,
        "opted_car_loan": joined_data.opted_car_loan,
        "recommend_nifty50": joined_data.recommend_nifty50,
        "recommend_elss": joined_data.recommend_elss,

        # --- CRITICAL: Volume Trackers (Required by dispatcher) ---
        "volTransLastStreamed_home": joined_data.volTransLastStreamed_home + joined_data.vol_increase,
        "volTransLastStreamed_car": joined_data.volTransLastStreamed_car + joined_data.vol_increase,
        "volTransLastStreamed_elss": joined_data.volTransLastStreamed_elss + joined_data.vol_increase,
        "volTransLastStreamed_nifty50": joined_data.volTransLastStreamed_nifty50 + joined_data.vol_increase,
        
        # --- CRITICAL: Tracking Columns (Required by dispatcher) ---
        "last_reach_out_home_loan": joined_data.last_reach_out_home_loan,
        "last_reach_out_car_loan": joined_data.last_reach_out_car_loan,
        "last_reach_out_nifty50": joined_data.last_reach_out_nifty50,
        "last_reach_out_elss": joined_data.last_reach_out_elss,
    }