"""
Simplified Schema Definitions
30 essential features for customer financial profiling
"""

import pathway as pw

# ==================== TRANSACTION SCHEMA ====================
class TransactionSchema(pw.Schema):
    """
    Live transaction stream schema
    Simple and clean structure for real-time processing
    """
    trans_id: int           # Unique transaction ID
    customer_id: int        # Customer identifier
    timestamp: int          # Unix timestamp
    trans_type: str         # "INCOME" or "EXPENSE"
    category: str           # Transaction category
    amount: float           # Transaction amount
    balance: float          # Account balance after transaction


# ==================== CUSTOMER PROFILE SCHEMA ====================
class CustomerProfileSchema(pw.Schema):
    """
    30 essential features for customer financial profile
    Computed from transaction history
    """
    # === Identity ===
    customer_id: int
    
    # === Transaction Counts (Features 1-3) ===
    total_transactions: int
    num_income: int
    num_expense: int
    
    # === Amount Aggregates (Features 4-9) ===
    total_income: float
    total_expense: float
    avg_income: float
    avg_expense: float
    median_income: float
    median_expense: float
    
    # === Statistical Measures (Features 10-13) ===
    std_income: float
    std_expense: float
    max_income: float
    max_expense: float
    
    # === Balance Analytics (Features 14-18) ===
    balance_current: float
    balance_avg: float
    balance_min: float
    balance_max: float
    balance_volatility: float
    
    # === Behavioral Metrics (Features 19-25) ===
    net_cashflow: float                 # Income - Expense
    income_expense_ratio: float         # Income / Expense
    avg_transaction_size: float         # Overall average
    transaction_frequency: float        # Transactions per day
    income_consistency: float           # 1 / CV of income
    expense_consistency: float          # 1 / CV of expense
    spending_rate: float                # Expense / Income
    
    # === Category Diversity (Features 26-28) ===
    unique_categories: int
    primary_category: str               # Most frequent category
    category_concentration: float       # % of transactions in primary category
    
    # === Temporal (Features 29-30) ===
    first_transaction_time: int
    last_transaction_time: int