# pipeline_config.py

# --- 1. HOME LOAN CONFIGURATION ---
HOME_LOAN_CONFIG = {
    "target": "opted_home_loan",
    "gmm_num_features": [
        'dti_ratio', 'savings_rate', 'income_to_limit', 'txn_intensity',
        'age_x_dependents', 'score_x_log_income', 'final_avg_monthly_balance'
    ],
    "gmm_cat_features": ['city_tier', 'education_level', 'marital_status', 'employment_type'],
    "nn_numerical_features": [
        'age', 'yearly_income', 'account_age_months', 'final_credit_score',
        'existing_loan_monthly_EMI_total', 'total_credit_limit', 'bounced_txn_count',
        'final_avg_monthly_balance', 'txn_count_last_30d', 'high_value_txn_count_30d',
        'dti_ratio', 'savings_rate', 'age_x_dependents', 'score_x_log_income'
    ],
    "nn_categorical_features": ['gender', 'marital_status', 'employment_type', 'occupation', 'education_level', 'city_tier'],
    "gif_title_prefix": "'Home Loan Taker'",
    "gif_filename": "home_loan_simulation.gif"
}

# --- 2. CAR LOAN CONFIGURATION ---
CAR_LOAN_CONFIG = {
    "target": "opted_car_loan",
    "gmm_num_features": [ # Added spend features
        'dti_ratio', 'savings_rate', 'score_x_log_income', 'final_avg_monthly_balance',
        'monthly_fuel_spend', 'monthly_transport_service_spend'
    ],
    "gmm_cat_features": ['city_tier', 'marital_status', 'employment_type'],
    "nn_numerical_features": [ # Added static and spend features
        'age', 'yearly_income', 'final_credit_score', 'bounced_txn_count',
        'final_avg_monthly_balance', 'dti_ratio', 'savings_rate', 'score_x_log_income',
        'has_existing_auto_loan', 'monthly_fuel_spend', 'monthly_transport_service_spend'
    ],
    "nn_categorical_features": ['gender', 'marital_status', 'employment_type', 'education_level', 'city_tier'],
    "gif_title_prefix": "'Car Loan Taker'",
    "gif_filename": "car_loan_simulation.gif"
}

# --- 3. NIFTY50 SIP RECOMMENDATION CONFIGURATION ---
NIFTY50_CONFIG = {
    "target": "recommend_nifty50",
    "gmm_num_features": [ # Focus on savings behavior
        'savings_rate', 'score_x_log_income', 'final_avg_monthly_balance',
        'avg_monthly_investment_debit'
    ],
    "gmm_cat_features": ['city_tier', 'education_level', 'employment_type'],
    "nn_numerical_features": [ # Focus on investment potential
        'age', 'yearly_income', 'final_credit_score', 'bounced_txn_count',
        'final_avg_monthly_balance', 'savings_rate', 'score_x_log_income',
        'has_existing_investment_account', 'avg_monthly_investment_debit'
    ],
    "nn_categorical_features": ['gender', 'marital_status', 'employment_type', 'education_level', 'city_tier'],
    "gif_title_prefix": "'Nifty50 Candidate'",
    "gif_filename": "nifty50_simulation.gif"
}

# --- 4. ELSS RECOMMENDATION CONFIGURATION ---
ELSS_CONFIG = {
    "target": "recommend_elss",
    "gmm_num_features": [ # Focus on savings and income
        'savings_rate', 'score_x_log_income', 'final_avg_monthly_balance',
        'avg_monthly_investment_debit'
    ],
    "gmm_cat_features": ['education_level', 'marital_status'], # Employment type is a hard rule, less needed here
    "nn_numerical_features": [ # Focus on tax-saving potential
        'age', 'yearly_income', 'final_credit_score', 'bounced_txn_count',
        'final_avg_monthly_balance', 'savings_rate', 'score_x_log_income',
        'avg_monthly_investment_debit'
    ],
    "nn_categorical_features": ['gender', 'marital_status', 'employment_type', 'education_level'],
    "gif_title_prefix": "'ELSS Candidate'",
    "gif_filename": "elss_simulation.gif"
}