# MASTERFILENode/schema.py
import pathway as pw

class MasterSchema(pw.Schema):
    # Static & Semi-Static Features
    customer_id: str
    age: int
    gender: str
    marital_status: str
    dependents_count: int
    employment_type: str
    occupation: str
    education_level: str
    city_tier: str
    yearly_income: float
    account_age_months: int
    initial_credit_score: int
    existing_loans_count: int
    existing_loan_monthly_EMI_total: float
    total_credit_limit: float
    initial_credit_utilization_ratio: float
    initial_avg_monthly_balance: float
    initial_savings_rate: float
    has_existing_auto_loan: int
    has_existing_investment_account: int

    # Final-state aggregated features
    txn_count_last_30d: float
    high_value_txn_count_30d: float
    bounced_txn_count: float
    final_avg_monthly_balance: float
    monthly_fuel_spend: float
    monthly_transport_service_spend: float
    avg_monthly_investment_debit: float
    final_credit_score: float

    # Final-state ratio/interaction features
    dti_ratio: float
    savings_rate: float
    income_to_limit: float
    txn_intensity: float
    age_x_dependents: float
    score_x_log_income: float

    # Target columns
    opted_home_loan: int
    opted_car_loan: int
    recommend_nifty50: int
    recommend_elss: int

    # Streaming architecture columns
    volTransLastStreamed_home: float
    volTransLastStreamed_car: float
    volTransLastStreamed_elss: float
    volTransLastStreamed_nifty50: float
    
    # Tracking columns
    last_reach_out_home_loan: str 
    last_reach_out_car_loan: str
    last_reach_out_nifty50: str
    last_reach_out_elss: str
    
    # FIX: Use str here for CSV loading (Convert to datetime in run_enrichment_node.py)
    last_update_timestamp: str