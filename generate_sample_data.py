"""
Sample Data Generator with Loan Types
Generates:
1. Initial customer profiles (1000 rows) with loan types
2. Historical transactions (used to compute initial profiles)
3. Live transaction stream (10 new transactions for testing)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# ==================== CONFIGURATION ====================
NUM_CUSTOMERS = 1000
TRANSACTIONS_PER_CUSTOMER = 50  # For historical data
NUM_LIVE_TRANSACTIONS = 10

# Transaction categories
INCOME_CATEGORIES = ["Salary", "Freelance", "Investment", "Bonus", "Refund"]
EXPENSE_CATEGORIES = ["Groceries", "Rent", "Utilities", "Entertainment", "Transportation", 
                      "Healthcare", "Shopping", "Dining", "Education", "Insurance"]

# Loan types
LOAN_TYPES = ["Home Loan", "Car Loan", "Personal Loan", "Education Loan", "Business Loan"]

# Base timestamp (start date: 2024-01-01)
BASE_TIMESTAMP = int(datetime(2024, 1, 1).timestamp())
CURRENT_TIMESTAMP = int(datetime.now().timestamp())


# ==================== HELPER FUNCTIONS ====================

def assign_loan_type_based_on_profile(features):
    """
    Assign loan type based on customer financial profile
    This creates realistic clustering patterns
    """
    income_expense_ratio = features['income_expense_ratio']
    avg_transaction_size = features['avg_transaction_size']
    balance_avg = features['balance_avg']
    spending_rate = features['spending_rate']
    
    # Home Loan: High balance, stable income/expense ratio, lower spending rate
    if balance_avg > 15000 and income_expense_ratio > 1.2 and spending_rate < 0.7:
        return "Home Loan"
    
    # Car Loan: Medium balance, moderate transaction size
    elif balance_avg > 8000 and avg_transaction_size > 150 and spending_rate < 0.8:
        return "Car Loan"
    
    # Education Loan: Lower balance, higher spending rate, younger profile
    elif balance_avg < 10000 and spending_rate > 0.75:
        return "Education Loan"
    
    # Business Loan: High transaction frequency, variable income
    elif features['transaction_frequency'] > 0.5 and features['income_consistency'] < 5.0:
        return "Business Loan"
    
    # Personal Loan: Default case
    else:
        return "Personal Loan"


def generate_customer_transactions(customer_id, num_transactions=50):
    """Generate realistic transaction history for a customer"""
    transactions = []
    
    # Starting balance
    balance = random.uniform(5000, 50000)
    
    # Income characteristics (varies by customer)
    monthly_income = random.uniform(2000, 10000)
    income_stability = random.uniform(0.7, 0.95)
    
    # Expense characteristics
    monthly_expense = monthly_income * random.uniform(0.6, 0.9)
    
    # Generate transactions over 6 months
    start_time = BASE_TIMESTAMP
    time_span = 180 * 24 * 3600  # 180 days in seconds
    
    for i in range(num_transactions):
        trans_id = customer_id * 10000 + i
        
        # Random timestamp within the period
        timestamp = start_time + random.randint(0, time_span)
        
        # Decide transaction type (more expenses than income)
        if random.random() < 0.25:  # 25% income
            trans_type = "INCOME"
            category = random.choice(INCOME_CATEGORIES)
            
            # Generate income amount with some variation
            base_amount = monthly_income / 4  # Weekly income
            amount = base_amount * random.uniform(income_stability, 1.2)
            
            balance += amount
        else:  # 75% expense
            trans_type = "EXPENSE"
            category = random.choice(EXPENSE_CATEGORIES)
            
            # Generate expense amount
            base_amount = monthly_expense / 20  # ~20 expenses per month
            amount = base_amount * random.uniform(0.1, 3.0)
            
            balance -= amount
            
            # Ensure balance doesn't go negative
            if balance < 0:
                balance = random.uniform(100, 1000)
        
        amount = round(amount, 2)
        balance = round(balance, 2)
        
        transactions.append({
            'trans_id': trans_id,
            'customer_id': customer_id,
            'timestamp': timestamp,
            'trans_type': trans_type,
            'category': category,
            'amount': amount,
            'balance': balance
        })
    
    return transactions


def compute_customer_features(customer_id, transactions_df):
    """Compute 30 features from transaction history"""
    
    # Filter transactions for this customer
    txns = transactions_df[transactions_df['customer_id'] == customer_id].copy()
    
    if len(txns) == 0:
        return None
    
    # Separate income and expense
    income_txns = txns[txns['trans_type'] == 'INCOME']
    expense_txns = txns[txns['trans_type'] == 'EXPENSE']
    
    # Transaction counts
    total_transactions = len(txns)
    num_income = len(income_txns)
    num_expense = len(expense_txns)
    
    # Amount aggregates
    total_income = income_txns['amount'].sum() if num_income > 0 else 0.0
    total_expense = expense_txns['amount'].sum() if num_expense > 0 else 0.0
    
    avg_income = income_txns['amount'].mean() if num_income > 0 else 0.0
    avg_expense = expense_txns['amount'].mean() if num_expense > 0 else 0.0
    
    median_income = income_txns['amount'].median() if num_income > 0 else 0.0
    median_expense = expense_txns['amount'].median() if num_expense > 0 else 0.0
    
    # Statistical measures
    std_income = income_txns['amount'].std() if num_income > 1 else 0.0
    std_expense = expense_txns['amount'].std() if num_expense > 1 else 0.0
    
    max_income = income_txns['amount'].max() if num_income > 0 else 0.0
    max_expense = expense_txns['amount'].max() if num_expense > 0 else 0.0
    
    # Balance analytics
    balance_current = txns['balance'].iloc[-1]
    balance_avg = txns['balance'].mean()
    balance_min = txns['balance'].min()
    balance_max = txns['balance'].max()
    balance_volatility = txns['balance'].std() / (balance_avg + 1.0)
    
    # Behavioral metrics
    net_cashflow = total_income - total_expense
    income_expense_ratio = total_income / (total_expense + 1.0)
    avg_transaction_size = txns['amount'].mean()
    
    # Transaction frequency (transactions per day)
    time_span_days = (txns['timestamp'].max() - txns['timestamp'].min()) / (24 * 3600)
    transaction_frequency = total_transactions / max(time_span_days, 1.0)
    
    # Consistency metrics (inverse of coefficient of variation)
    income_consistency = avg_income / (std_income + 1.0) if num_income > 0 else 0.0
    expense_consistency = avg_expense / (std_expense + 1.0) if num_expense > 0 else 0.0
    
    spending_rate = total_expense / (total_income + 1.0)
    
    # Category diversity
    unique_categories = txns['category'].nunique()
    category_counts = txns['category'].value_counts()
    primary_category = category_counts.index[0] if len(category_counts) > 0 else ""
    category_concentration = category_counts.iloc[0] / total_transactions if len(category_counts) > 0 else 0.0
    
    # Temporal
    first_transaction_time = int(txns['timestamp'].min())
    last_transaction_time = int(txns['timestamp'].max())
    
    features = {
        'customer_id': customer_id,
        'total_transactions': total_transactions,
        'num_income': num_income,
        'num_expense': num_expense,
        'total_income': round(total_income, 2),
        'total_expense': round(total_expense, 2),
        'avg_income': round(avg_income, 2),
        'avg_expense': round(avg_expense, 2),
        'median_income': round(median_income, 2),
        'median_expense': round(median_expense, 2),
        'std_income': round(std_income, 2),
        'std_expense': round(std_expense, 2),
        'max_income': round(max_income, 2),
        'max_expense': round(max_expense, 2),
        'balance_current': round(balance_current, 2),
        'balance_avg': round(balance_avg, 2),
        'balance_min': round(balance_min, 2),
        'balance_max': round(balance_max, 2),
        'balance_volatility': round(balance_volatility, 4),
        'net_cashflow': round(net_cashflow, 2),
        'income_expense_ratio': round(income_expense_ratio, 4),
        'avg_transaction_size': round(avg_transaction_size, 2),
        'transaction_frequency': round(transaction_frequency, 4),
        'income_consistency': round(income_consistency, 4),
        'expense_consistency': round(expense_consistency, 4),
        'spending_rate': round(spending_rate, 4),
        'unique_categories': unique_categories,
        'primary_category': primary_category,
        'category_concentration': round(category_concentration, 4),
        'first_transaction_time': first_transaction_time,
        'last_transaction_time': last_transaction_time
    }
    
    # Assign loan type based on profile
    loan_type = assign_loan_type_based_on_profile(features)
    features['loan_type'] = loan_type
    
    return features


def generate_live_transactions(num_transactions=10):
    """Generate live transactions for testing"""
    transactions = []
    
    # Random customers from our dataset
    customer_ids = random.sample(range(1, NUM_CUSTOMERS + 1), min(num_transactions, NUM_CUSTOMERS))
    
    for i, customer_id in enumerate(customer_ids):
        trans_id = 1000000 + i
        timestamp = CURRENT_TIMESTAMP + i * 60  # Space transactions by 1 minute
        
        # Random transaction
        if random.random() < 0.3:  # 30% income
            trans_type = "INCOME"
            category = random.choice(INCOME_CATEGORIES)
            amount = round(random.uniform(500, 5000), 2)
        else:  # 70% expense
            trans_type = "EXPENSE"
            category = random.choice(EXPENSE_CATEGORIES)
            amount = round(random.uniform(10, 500), 2)
        
        balance = round(random.uniform(1000, 50000), 2)
        
        transactions.append({
            'trans_id': trans_id,
            'customer_id': customer_id,
            'timestamp': timestamp,
            'trans_type': trans_type,
            'category': category,
            'amount': amount,
            'balance': balance
        })
    
    return transactions


# ==================== MAIN GENERATION ====================

def main():
    print("=" * 70)
    print("Sample Data Generator with Loan Types")
    print("=" * 70)
    
    # 1. Generate historical transactions
    print("\n[1/4] Generating historical transactions...")
    all_transactions = []
    
    for customer_id in range(1, NUM_CUSTOMERS + 1):
        txns = generate_customer_transactions(customer_id, TRANSACTIONS_PER_CUSTOMER)
        all_transactions.extend(txns)
        
        if customer_id % 100 == 0:
            print(f"  Generated transactions for {customer_id} customers...")
    
    transactions_df = pd.DataFrame(all_transactions)
    transactions_df = transactions_df.sort_values('timestamp')
    
    print(f"  ✓ Generated {len(transactions_df)} transactions for {NUM_CUSTOMERS} customers")
    
    # 2. Compute customer features
    print("\n[2/4] Computing customer features with loan types...")
    customer_features = []
    
    for customer_id in range(1, NUM_CUSTOMERS + 1):
        features = compute_customer_features(customer_id, transactions_df)
        if features:
            customer_features.append(features)
        
        if customer_id % 100 == 0:
            print(f"  Computed features for {customer_id} customers...")
    
    customer_df = pd.DataFrame(customer_features)
    print(f"  ✓ Computed features for {len(customer_df)} customers")
    
    # Print loan type distribution
    print("\n  Loan Type Distribution:")
    loan_dist = customer_df['loan_type'].value_counts()
    for loan_type, count in loan_dist.items():
        print(f"    {loan_type}: {count} customers ({count/len(customer_df)*100:.1f}%)")
    
    # 3. Generate live transactions
    print("\n[3/4] Generating live transaction stream...")
    live_transactions = generate_live_transactions(NUM_LIVE_TRANSACTIONS)
    live_df = pd.DataFrame(live_transactions)
    print(f"  ✓ Generated {len(live_df)} live transactions")
    
    # 4. Save to CSV
    print("\n[4/4] Saving to CSV files...")
    
    # Save customer profiles
    customer_df.to_csv('data/customer_profiles.csv', index=False)
    print(f"  ✓ Saved customer_profiles.csv ({len(customer_df)} rows)")
    
    # Save historical transactions (for reference)
    transactions_df.to_csv('data/historical_transactions.csv', index=False)
    print(f"  ✓ Saved historical_transactions.csv ({len(transactions_df)} rows)")
    
    # Save live transactions
    live_df.to_csv('data/live_transactions.csv', index=False)
    print(f"  ✓ Saved live_transactions.csv ({len(live_df)} rows)")
    
    # Print sample data
    print("\n" + "=" * 70)
    print("SAMPLE DATA")
    print("=" * 70)
    
    print("\n--- Customer Profile Sample (First 5 Customers) ---")
    print(customer_df[['customer_id', 'loan_type', 'balance_avg', 'income_expense_ratio', 'spending_rate']].head(5).to_string())
    
    print("\n--- Live Transactions Sample ---")
    print(live_df.to_string())
    
    print("\n" + "=" * 70)
    print("Data generation complete!")
    print("=" * 70)
    print("\nFiles created in 'data/' directory:")
    print("  1. customer_profiles.csv - 1000 customers with 31 features (including loan_type)")
    print("  2. historical_transactions.csv - 50,000 historical transactions")
    print("  3. live_transactions.csv - 10 live transactions for testing")
    print("\nYou can now run the pipeline to process live transactions!")


if __name__ == "__main__":
    import os
    os.makedirs('data', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    main()