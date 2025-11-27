# generate_data.py

import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('en_IN')
NUM_CUSTOMERS = 1250 # Kept at 12500 for the 10000/2500 split
MONTHS_OF_DATA = 4
START_DATE = datetime(2023, 1, 1)
HIGH_VALUE_TXN_THRESHOLD = 75000

def define_archetypes_as_recipes():
    recipes = {
        # --- MODIFIED: Adjusted weights ---
        'Urban_Tech_Couples': {'weight': 0.22, 'age_range': (27, 33), 'city_tier': ['tier1'], 'marital_status': ['Married'], 'dependents': [0, 1], 'employment': ['Salaried'], 'occupation': ['Software Engineer', 'Product Manager', 'Data Scientist'], 'education': ['Post-Graduate'], 'income_base': 2_200_000, 'credit_score_base': 760, 'initial_dti_range': (0.2, 0.35), 'savings_rate_range': (0.2, 0.3), 'monthly_txn_base': 35,
                               'has_existing_auto_loan': True, 'has_existing_investment_account': True, 'txn_category_dist': {'Fuel': 0.2, 'Investment': 0.2, 'Shopping': 0.3, 'Utilities': 0.15, 'Transport': 0.05, 'Misc': 0.1}},
        'Tier2_Business_Owners': {'weight': 0.15, 'age_range': (35, 50), 'city_tier': ['tier2'], 'marital_status': ['Married'], 'dependents': [1, 2, 3], 'employment': ['Self-Employed'], 'occupation': ['Business Owner', 'Trader'], 'education': ['Graduate'], 'income_base': 3_000_000, 'credit_score_base': 740, 'initial_dti_range': (0.15, 0.3), 'savings_rate_range': (0.25, 0.4), 'monthly_txn_base': 30,
                                   'has_existing_auto_loan': True, 'has_existing_investment_account': True, 'txn_category_dist': {'Fuel': 0.3, 'Investment': 0.15, 'Shopping': 0.2, 'Utilities': 0.1, 'Transport': 0.05, 'Misc': 0.2}},
        'Independent_Women_Earners': {'weight': 0.14, 'age_range': (28, 38), 'city_tier': ['tier1', 'tier2'], 'marital_status': ['Single'], 'dependents': [0], 'employment': ['Salaried'], 'occupation': ['HR Manager', 'Architect'], 'education': ['Post-Graduate'], 'income_base': 1_800_000, 'credit_score_base': 770, 'initial_dti_range': (0.1, 0.25), 'savings_rate_range': (0.2, 0.35), 'monthly_txn_base': 40,
                                          'has_existing_auto_loan': random.choice([True, False]), 'has_existing_investment_account': True, 'txn_category_dist': {'Fuel': 0.1, 'Investment': 0.2, 'Shopping': 0.3, 'Utilities': 0.1, 'Transport': 0.2, 'Misc': 0.1}},
        'Govt_Employees': {'weight': 0.10, 'age_range': (40, 55), 'city_tier': ['tier2', 'tier3'], 'marital_status': ['Married'], 'dependents': [1, 2], 'employment': ['Salaried'], 'occupation': ['Govt. Employee'], 'education': ['Graduate'], 'income_base': 1_500_000, 'credit_score_base': 780, 'initial_dti_range': (0.2, 0.3), 'savings_rate_range': (0.25, 0.4), 'monthly_txn_base': 25,
                             'has_existing_auto_loan': False, 'has_existing_investment_account': True, 'txn_category_dist': {'Fuel': 0.25, 'Investment': 0.1, 'Shopping': 0.2, 'Utilities': 0.25, 'Transport': 0.05, 'Misc': 0.15}},
        'Financially_Stressed': {'weight': 0.18, 'age_range': (25, 45), 'city_tier': ['tier1', 'tier2', 'tier3'], 'marital_status': ['Single', 'Married'], 'dependents': [0, 1, 2], 'employment': ['Salaried', 'Self-Employed'], 'occupation': ['Sales Rep', 'Gig Worker'], 'education': ['Under-Graduate'], 'income_base': 600_000, 'credit_score_base': 620, 'initial_dti_range': (0.4, 0.65), 'savings_rate_range': (0.02, 0.1), 'monthly_txn_base': 50,
                                   'has_existing_auto_loan': False, 'has_existing_investment_account': False, 'txn_category_dist': {'Fuel': 0.05, 'Investment': 0.0, 'Shopping': 0.3, 'Utilities': 0.2, 'Transport': 0.35, 'Misc': 0.1}},
        'High_Net_Worth': {'weight': 0.05, 'age_range': (45, 60), 'city_tier': ['tier1'], 'marital_status': ['Married'], 'dependents': [1, 2], 'employment': ['Self-Employed'], 'occupation': ['CXO', 'Surgeon', 'Investor'], 'education': ['Post-Graduate'], 'income_base': 9_000_000, 'credit_score_base': 820, 'initial_dti_range': (0.1, 0.2), 'savings_rate_range': (0.4, 0.6), 'monthly_txn_base': 28,
                             'has_existing_auto_loan': True, 'has_existing_investment_account': True, 'txn_category_dist': {'Fuel': 0.15, 'Investment': 0.4, 'Shopping': 0.2, 'Utilities': 0.1, 'Transport': 0.05, 'Misc': 0.1}},
        'Stable_Renters': {'weight': 0.08, 'age_range': (26, 35), 'city_tier': ['tier1', 'tier2'], 'marital_status': ['Single'], 'dependents': [0, 1], 'employment': ['Salaried'], 'occupation': ['Analyst', 'Teacher'], 'education': ['Graduate'], 'income_base': 1_000_000, 'credit_score_base': 710, 'initial_dti_range': (0.15, 0.3), 'savings_rate_range': (0.1, 0.2), 'monthly_txn_base': 30,
                             'has_existing_auto_loan': False, 'has_existing_investment_account': random.choice([True, False]), 'txn_category_dist': {'Fuel': 0.1, 'Investment': 0.05, 'Shopping': 0.25, 'Utilities': 0.2, 'Transport': 0.3, 'Misc': 0.1}},

        # --- NEW ARCHETYPE to boost nifty50 recommendations ---
        'First_Time_Professionals': {'weight': 0.08, 'age_range': (23, 28), 'city_tier': ['tier1', 'tier2'], 'marital_status': ['Single'], 'dependents': [0], 'employment': ['Salaried'], 'occupation': ['Analyst', 'Junior Software Engineer', 'Consultant'], 'education': ['Graduate'], 'income_base': 900_000, 'credit_score_base': 740, 'initial_dti_range': (0.1, 0.25), 'savings_rate_range': (0.1, 0.2), 'monthly_txn_base': 40,
                                     'has_existing_auto_loan': False, 'has_existing_investment_account': False, 'txn_category_dist': {'Fuel': 0.05, 'Investment': 0.05, 'Shopping': 0.3, 'Utilities': 0.2, 'Transport': 0.3, 'Misc': 0.1}}
    }
    return recipes

# --- All other functions (generate_customers, generate_transactions, etc.) remain exactly the same as before ---

def generate_customers(num_customers):
    recipes = define_archetypes_as_recipes()
    recipe_names = list(recipes.keys())
    recipe_weights = [recipes[name]['weight'] for name in recipe_names]
    customers_data = []
    for i in range(num_customers):
        cust_id = f'CUST_{i+1:06d}'
        recipe_name = random.choices(recipe_names, weights=recipe_weights, k=1)[0]
        props = recipes[recipe_name]
        age = random.randint(*props['age_range'])
        yearly_income = props['income_base'] * random.uniform(0.85, 1.25)
        credit_score = np.clip(int(props['credit_score_base'] + np.random.normal(0, 30)), 300, 900)
        initial_dti = random.uniform(*props['initial_dti_range'])
        was_interested = (credit_score > 680 and yearly_income > 800_000 and initial_dti < 0.5)
        
        customers_data.append({
            'customer_id': cust_id, 'internal_recipe': recipe_name, 'age': age,
            'gender': random.choice(['Male', 'Female']), 'marital_status': random.choice(props['marital_status']),
            'dependents_count': random.choice(props['dependents']), 'employment_type': random.choice(props['employment']),
            'occupation': random.choice(props['occupation']), 'education_level': random.choice(props['education']),
            'city_tier': random.choice(props['city_tier']), 'yearly_income': round(yearly_income, 2),
            'account_age_months': random.randint(12, (age - 18) * 12), 'initial_credit_score': credit_score,
            'existing_loans_count': random.randint(0, 3), 'existing_loan_monthly_EMI_total': round((yearly_income/12)*initial_dti, 2),
            'total_credit_limit': round(yearly_income * random.uniform(0.3, 0.9), 2),
            'initial_credit_utilization_ratio': round(random.uniform(0.1, 0.8), 2),
            'initial_avg_monthly_balance': round((yearly_income/12) * random.uniform(*props['savings_rate_range']), 2),
            'initial_savings_rate': round(random.uniform(*props['savings_rate_range']), 2),
            'was_interested': was_interested,
            'has_existing_auto_loan': 1 if props['has_existing_auto_loan'] else 0,
            'has_existing_investment_account': 1 if props['has_existing_investment_account'] else 0,
        })
    return pd.DataFrame(customers_data)

def generate_transactions(customers_df, months, start_date):
    transactions = []
    recipes = define_archetypes_as_recipes()
    final_credit_scores = {}

    for _, customer in customers_df.iterrows():
        props = recipes[customer['internal_recipe']]
        base_monthly_income = customer['yearly_income'] / 12
        current_balance = customer['initial_avg_monthly_balance']
        current_score = customer['initial_credit_score']
        category_dist = props['txn_category_dist']
        
        for month in range(months):
            shock = random.gauss(0, 0.05); this_month_income = base_monthly_income * (1 + shock)
            if month == 2: this_month_income += base_monthly_income * 0.5
            
            salary_date = start_date + timedelta(days=month*30 + random.randint(1, 5))
            transactions.append({'customer_id': customer['customer_id'], 'txn_datetime': salary_date, 'txn_amount': this_month_income, 'txn_type': 'CREDIT', 'balance_after_txn': current_balance + this_month_income, 'bounced_flag': False, 'txn_category': 'Salary'})
            current_balance += this_month_income
            
            emi = customer['existing_loan_monthly_EMI_total']
            if emi > 0:
                emi_date = start_date + timedelta(days=month*30 + random.randint(6, 10))
                bounced = current_balance < emi
                if bounced: current_score = max(300, current_score - random.randint(10, 20))
                else: current_score = min(900, current_score + random.randint(1, 3)); current_balance -= emi
                transactions.append({'customer_id': customer['customer_id'], 'txn_datetime': emi_date, 'txn_amount': -emi, 'txn_type': 'DEBIT', 'balance_after_txn': current_balance, 'bounced_flag': bounced, 'txn_category': 'EMI'})
            
            num_txns = props['monthly_txn_base'] + random.randint(-5, 5)
            if current_balance < base_monthly_income * 0.3: num_txns = int(num_txns * 0.6)

            for _ in range(num_txns):
                txn_date = start_date + timedelta(days=month*30 + random.randint(1, 30))
                if current_balance > base_monthly_income * 2: amount = -random.uniform(1000, 8000)
                else: amount = -random.uniform(200, 3000)

                category = random.choices(list(category_dist.keys()), weights=list(category_dist.values()), k=1)[0]
                
                if current_balance >= abs(amount):
                    transactions.append({'customer_id': customer['customer_id'], 'txn_datetime': txn_date, 'txn_amount': amount, 'txn_type': 'DEBIT', 'balance_after_txn': current_balance + amount, 'bounced_flag': False, 'txn_category': category})
                    current_balance += amount
                else:
                    transactions.append({'customer_id': customer['customer_id'], 'txn_datetime': txn_date, 'txn_amount': amount, 'txn_type': 'DEBIT', 'balance_after_txn': current_balance, 'bounced_flag': True, 'txn_category': category})
        final_credit_scores[customer['customer_id']] = current_score
    return pd.DataFrame(transactions), final_credit_scores

def calculate_advanced_features(df):
    monthly_income = df['yearly_income'] / 12
    df['dti_ratio'] = df['existing_loan_monthly_EMI_total'] / (monthly_income + 1)
    df['savings_rate'] = df['final_avg_monthly_balance'] / (monthly_income + 1)
    df['income_to_limit'] = df['yearly_income'] / (df['total_credit_limit'] + 1)
    df['txn_intensity'] = df['txn_count_last_30d'] / (df['yearly_income'] / 10000 + 1)
    df['age_x_dependents'] = df['age'] * df['dependents_count']
    df['score_x_log_income'] = df['final_credit_score'] * np.log1p(df['yearly_income'])
    return df

def update_customers_with_txn_data(customers, transactions, final_scores):
    aggs = transactions.groupby('customer_id').agg(
        txn_count_last_30d=('txn_amount', 'size'),
        high_value_txn_count_30d=('txn_amount', lambda x: (x.abs() > HIGH_VALUE_TXN_THRESHOLD).sum()),
        bounced_txn_count=('bounced_flag', 'sum'),
        final_avg_monthly_balance=('balance_after_txn', 'mean')
    ).reset_index()
    
    debit_txns = transactions[transactions['txn_type'] == 'DEBIT'].copy()
    debit_txns['txn_amount'] = debit_txns['txn_amount'].abs()
    
    category_spends = debit_txns.pivot_table(
        index='customer_id', 
        columns='txn_category', 
        values='txn_amount', 
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    
    spend_cols = ['Fuel', 'Transport', 'Investment']
    for col in spend_cols:
        if col not in category_spends.columns: category_spends[col] = 0
        category_spends[col] /= MONTHS_OF_DATA
    
    category_spends = category_spends.rename(columns={
        'Fuel': 'monthly_fuel_spend',
        'Transport': 'monthly_transport_service_spend',
        'Investment': 'avg_monthly_investment_debit'
    })
    
    cust_upd = pd.merge(customers, aggs, on='customer_id', how='left')
    cust_upd = pd.merge(cust_upd, category_spends[['customer_id'] + [c for c in ['monthly_fuel_spend', 'monthly_transport_service_spend', 'avg_monthly_investment_debit'] if c in category_spends.columns]], on='customer_id', how='left')
    cust_upd = cust_upd.fillna(0)
    
    cust_upd['final_credit_score'] = cust_upd['customer_id'].map(final_scores)
    cust_upd = calculate_advanced_features(cust_upd)

    # Home Loan Target
    score_hl = (cust_upd['yearly_income'] > 1_200_000).astype(int) * 2 + (cust_upd['city_tier'] == 'tier1').astype(int) + (cust_upd['final_credit_score'] > 750).astype(int) * 3 - (cust_upd['dti_ratio'] > 0.4).astype(int) * 2 - (cust_upd['bounced_txn_count'] > 0).astype(int) * 4
    prob_hl = 1 / (1 + np.exp(-score_hl))
    prob_hl = np.where(cust_upd['was_interested'] == False, prob_hl * 0.3, prob_hl)
    cust_upd['opted_home_loan'] = (np.random.rand(len(cust_upd)) < prob_hl).astype(int)
    
    # Car Loan Target
    score_cl = (cust_upd['yearly_income'] > 900_000).astype(int) * 2 + (cust_upd['final_credit_score'] > 720).astype(int) * 3 + (cust_upd['monthly_transport_service_spend'] > 3000).astype(int) * 3 - (cust_upd['has_existing_auto_loan'] == 1).astype(int) * 5 - (cust_upd['dti_ratio'] > 0.45).astype(int) * 2
    prob_cl = 1 / (1 + np.exp(-score_cl))
    cust_upd['opted_car_loan'] = (np.random.rand(len(cust_upd)) < prob_cl).astype(int)

    # Nifty 50 Recommendation Target
    cond_nifty50 = ((cust_upd['yearly_income'] > 700_000) & (cust_upd['final_credit_score'] > 700) & (cust_upd['age'] < 45) & (cust_upd['has_existing_investment_account'] == 0))
    cust_upd['recommend_nifty50'] = np.where(cond_nifty50, 1, 0)
    
    # ELSS Recommendation Target
    cond_elss = ((cust_upd['employment_type'] == 'Salaried') & (cust_upd['yearly_income'] > 800_000) & (cust_upd['avg_monthly_investment_debit'] < (cust_upd['yearly_income']/12 * 0.1)))
    cust_upd['recommend_elss'] = np.where(cond_elss, 1, 0)

    return cust_upd.drop(columns=['internal_recipe', 'was_interested'])

def create_and_save_data():
    print("Generating Multi-Product Customer Data...")
    df = generate_customers(NUM_CUSTOMERS)
    txns, final_scores = generate_transactions(df, MONTHS_OF_DATA, START_DATE)
    final_df = update_customers_with_txn_data(df, txns, final_scores)
    
    final_df.to_csv('customers_master_multi_product.csv', index=False)
    txns.to_csv('transactions_history_categorized.csv', index=False)
    print("Multi-product data saved.")
    return final_df

if __name__ == '__main__':
    create_and_save_data()