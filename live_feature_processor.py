"""
Live Feature Processor with NATS and Loan Recommendations
Computes 30 customer features in real-time from transaction streams
Detects portfolio changes and recommends loans
"""

import pathway as pw
import numpy as np
import os
import csv
from datetime import datetime
from loan_recommender import LoanRecommender

# Import schemas
from schemas import TransactionSchema, CustomerProfileSchema

# Create output directory
os.makedirs("output", exist_ok=True)

# ==================== CONFIGURATION ====================
NATS_URL = "nats://localhost:4222/"
TRANSACTION_TOPIC = "transactions.live"
FEATURES_TOPIC = "features.customer"
SIMILARITY_THRESHOLD = 85.0  # Portfolio similarity threshold (%)
RECOMMENDATIONS_CSV = "output/loan_recommendations.csv"

print("=" * 70)
print("Live Feature Processor with Loan Recommendations")
print("=" * 70)
print(f"\nNATS Server: {NATS_URL}")
print(f"Subscribing to: {TRANSACTION_TOPIC}")
print(f"Publishing to: {FEATURES_TOPIC}")
print(f"Similarity Threshold: {SIMILARITY_THRESHOLD}%")
print(f"Recommendations CSV: {RECOMMENDATIONS_CSV}")
print()

# Initialize recommendations CSV file with headers
def initialize_recommendations_csv():
    """Initialize the recommendations CSV file with headers"""
    with open(RECOMMENDATIONS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp',
            'customer_id',
            'event_type',
            'portfolio_similarity',
            'previous_loan_type',
            'recommended_loan_type',
            'balance_current',
            'balance_avg',
            'income_expense_ratio',
            'spending_rate',
            'transaction_frequency',
            'total_transactions',
            'avg_transaction_size'
        ])

# Initialize CSV file
initialize_recommendations_csv()
print(f"✓ Initialized recommendations CSV: {RECOMMENDATIONS_CSV}\n")

# Load loan recommender model
print("Loading loan recommendation model...")
recommender = LoanRecommender()
if recommender.load_model():
    print(f"✓ Model loaded successfully")
    print(f"  - {len(recommender.customer_baseline_portfolios)} customers in baseline")
    print(f"  - {len(recommender.loan_type_mapping)} loan type clusters")
else:
    print("❌ Model not found! Please run: python loan_recommender.py")
    exit(1)
print()

# ==================== USER-DEFINED FUNCTIONS ====================

@pw.udf
def safe_mean(values: tuple) -> float:
    """Calculate mean from tuple of values"""
    arr = np.array([v for v in values if v is not None])
    return float(np.mean(arr)) if len(arr) > 0 else 0.0


@pw.udf
def safe_median(values: tuple) -> float:
    """Calculate median from tuple of values"""
    arr = np.array([v for v in values if v is not None])
    return float(np.median(arr)) if len(arr) > 0 else 0.0


@pw.udf
def safe_std(values: tuple) -> float:
    """Calculate standard deviation from tuple of values"""
    arr = np.array([v for v in values if v is not None])
    return float(np.std(arr)) if len(arr) > 1 else 0.0


@pw.udf
def safe_max(values: tuple) -> float:
    """Safely get maximum value"""
    arr = [v for v in values if v is not None]
    return float(max(arr)) if len(arr) > 0 else 0.0


@pw.udf
def safe_min(values: tuple) -> float:
    """Safely get minimum value"""
    arr = [v for v in values if v is not None]
    return float(min(arr)) if len(arr) > 0 else 0.0


@pw.udf
def count_unique(values: tuple) -> int:
    """Count unique values"""
    unique = set([v for v in values if v not in (None, "")])
    return len(unique)


@pw.udf
def most_frequent(values: tuple) -> str:
    """Get most frequent value"""
    if not values:
        return ""
    
    from collections import Counter
    counts = Counter([v for v in values if v not in (None, "")])
    
    if len(counts) == 0:
        return ""
    
    return counts.most_common(1)[0][0]


@pw.udf
def category_concentration_calc(values: tuple) -> float:
    """Calculate concentration of primary category"""
    if not values or len(values) == 0:
        return 0.0
    
    from collections import Counter
    counts = Counter([v for v in values if v not in (None, "")])
    
    if len(counts) == 0:
        return 0.0
    
    max_count = counts.most_common(1)[0][1]
    return float(max_count) / len(values)


def write_recommendation_to_csv(
    customer_id,
    event_type,
    similarity,
    previous_loan,
    recommended_loan,
    balance_current,
    balance_avg,
    income_expense_ratio,
    spending_rate,
    transaction_frequency,
    total_transactions,
    avg_transaction_size
):
    """Write loan recommendation to CSV file"""
    try:
        with open(RECOMMENDATIONS_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                customer_id,
                event_type,
                f"{similarity:.2f}",
                previous_loan,
                recommended_loan,
                f"{balance_current:.2f}",
                f"{balance_avg:.2f}",
                f"{income_expense_ratio:.4f}",
                f"{spending_rate:.4f}",
                f"{transaction_frequency:.4f}",
                total_transactions,
                f"{avg_transaction_size:.2f}"
            ])
    except Exception as e:
        print(f"Error writing to CSV: {e}")


@pw.udf
def check_loan_recommendation(
    customer_id: int,
    total_transactions: int,
    num_income: int,
    num_expense: int,
    total_income: float,
    total_expense: float,
    avg_income: float,
    avg_expense: float,
    median_income: float,
    median_expense: float,
    std_income: float,
    std_expense: float,
    max_income: float,
    max_expense: float,
    balance_current: float,
    balance_avg: float,
    balance_min: float,
    balance_max: float,
    balance_volatility: float,
    net_cashflow: float,
    income_expense_ratio: float,
    avg_transaction_size: float,
    transaction_frequency: float,
    income_consistency: float,
    expense_consistency: float,
    spending_rate: float,
    unique_categories: int,
    category_concentration: float,
) -> str:
    """
    Check if portfolio changed and return loan recommendation
    Also writes to CSV file
    """
    # Create features dictionary
    features = {
        'total_transactions': total_transactions,
        'num_income': num_income,
        'num_expense': num_expense,
        'total_income': total_income,
        'total_expense': total_expense,
        'avg_income': avg_income,
        'avg_expense': avg_expense,
        'median_income': median_income,
        'median_expense': median_expense,
        'std_income': std_income,
        'std_expense': std_expense,
        'max_income': max_income,
        'max_expense': max_expense,
        'balance_current': balance_current,
        'balance_avg': balance_avg,
        'balance_min': balance_min,
        'balance_max': balance_max,
        'balance_volatility': balance_volatility,
        'net_cashflow': net_cashflow,
        'income_expense_ratio': income_expense_ratio,
        'avg_transaction_size': avg_transaction_size,
        'transaction_frequency': transaction_frequency,
        'income_consistency': income_consistency,
        'expense_consistency': expense_consistency,
        'spending_rate': spending_rate,
        'unique_categories': unique_categories,
        'category_concentration': category_concentration,
    }
    
    # Check portfolio change
    changed, similarity, recommended_loan, current_loan = recommender.check_portfolio_change(
        customer_id, features, SIMILARITY_THRESHOLD
    )
    
    if changed:
        if current_loan == "NEW_CUSTOMER":
            # New customer detected
            message = f"✓ NEW CUSTOMER {customer_id} → Recommended: {recommended_loan}"
            print(message)
            
            # Write to CSV
            write_recommendation_to_csv(
                customer_id=customer_id,
                event_type="NEW_CUSTOMER",
                similarity=0.0,
                previous_loan="N/A",
                recommended_loan=recommended_loan,
                balance_current=balance_current,
                balance_avg=balance_avg,
                income_expense_ratio=income_expense_ratio,
                spending_rate=spending_rate,
                transaction_frequency=transaction_frequency,
                total_transactions=total_transactions,
                avg_transaction_size=avg_transaction_size
            )
            
            return f"NEW:{recommended_loan}"
        else:
            # Portfolio changed
            message = f"⚠️  PORTFOLIO CHANGE: Customer {customer_id} | Similarity: {similarity:.2f}% | {current_loan} → {recommended_loan}"
            print(message)
            
            # Write to CSV
            write_recommendation_to_csv(
                customer_id=customer_id,
                event_type="PORTFOLIO_CHANGE",
                similarity=similarity,
                previous_loan=current_loan,
                recommended_loan=recommended_loan,
                balance_current=balance_current,
                balance_avg=balance_avg,
                income_expense_ratio=income_expense_ratio,
                spending_rate=spending_rate,
                transaction_frequency=transaction_frequency,
                total_transactions=total_transactions,
                avg_transaction_size=avg_transaction_size
            )
            
            return f"CHANGE:{recommended_loan}"
    
    return f"STABLE:{current_loan}"


# ==================== DATA INGESTION ====================

# Read live transactions from NATS
print("[1/3] Connecting to NATS and subscribing to transaction stream...")
transactions = pw.io.nats.read(
    NATS_URL,
    topic=TRANSACTION_TOPIC,
    schema=TransactionSchema,
    format="json",
)
print("✓ Connected to transaction stream\n")

# ==================== FEATURE COMPUTATION ====================

print("[2/3] Setting up feature computation pipeline...")

# Add derived columns
transactions = transactions.select(
    *pw.this,
    is_income=pw.if_else(pw.this.trans_type == "INCOME", 1, 0),
    is_expense=pw.if_else(pw.this.trans_type == "EXPENSE", 1, 0),
)

# Base aggregation by customer
aggregated = transactions.groupby(pw.this.customer_id).reduce(
    customer_id=pw.this.customer_id,
    
    # Transaction counts
    total_transactions=pw.reducers.count(),
    num_income=pw.reducers.sum(pw.this.is_income),
    num_expense=pw.reducers.sum(pw.this.is_expense),
    
    # Amount totals
    total_income=pw.reducers.sum(
        pw.if_else(pw.this.is_income == 1, pw.this.amount, 0.0)
    ),
    total_expense=pw.reducers.sum(
        pw.if_else(pw.this.is_expense == 1, pw.this.amount, 0.0)
    ),
    
    # Collect amounts for statistics
    all_income_amounts=pw.reducers.tuple(
        pw.if_else(pw.this.is_income == 1, pw.this.amount, None)
    ),
    all_expense_amounts=pw.reducers.tuple(
        pw.if_else(pw.this.is_expense == 1, pw.this.amount, None)
    ),
    all_amounts=pw.reducers.tuple(pw.this.amount),
    
    # Balance tracking
    all_balances=pw.reducers.tuple(pw.this.balance),
    balance_current=pw.reducers.any(pw.this.balance),
    
    # Category analysis
    all_categories=pw.reducers.tuple(pw.this.category),
    
    # Temporal tracking
    first_transaction_time=pw.reducers.min(pw.this.timestamp),
    last_transaction_time=pw.reducers.max(pw.this.timestamp),
)

# Compute derived statistics
features = aggregated.select(
    customer_id=pw.this.customer_id,
    
    # === Transaction Counts (Features 1-3) ===
    total_transactions=pw.this.total_transactions,
    num_income=pw.this.num_income,
    num_expense=pw.this.num_expense,
    
    # === Amount Aggregates (Features 4-9) ===
    total_income=pw.this.total_income,
    total_expense=pw.this.total_expense,
    avg_income=safe_mean(pw.this.all_income_amounts),
    avg_expense=safe_mean(pw.this.all_expense_amounts),
    median_income=safe_median(pw.this.all_income_amounts),
    median_expense=safe_median(pw.this.all_expense_amounts),
    
    # === Statistical Measures (Features 10-13) ===
    std_income=safe_std(pw.this.all_income_amounts),
    std_expense=safe_std(pw.this.all_expense_amounts),
    max_income=safe_max(pw.this.all_income_amounts),
    max_expense=safe_max(pw.this.all_expense_amounts),
    
    # === Balance Analytics (Features 14-18) ===
    balance_current=pw.this.balance_current,
    balance_avg=safe_mean(pw.this.all_balances),
    balance_min=safe_min(pw.this.all_balances),
    balance_max=safe_max(pw.this.all_balances),
    balance_std=safe_std(pw.this.all_balances),
    
    # === Category Diversity (Features 26-28) ===
    unique_categories=count_unique(pw.this.all_categories),
    primary_category=most_frequent(pw.this.all_categories),
    category_concentration=category_concentration_calc(pw.this.all_categories),
    
    # === Temporal (Features 29-30) ===
    first_transaction_time=pw.this.first_transaction_time,
    last_transaction_time=pw.this.last_transaction_time,
    
    # Store for next calculation
    avg_income_temp=safe_mean(pw.this.all_income_amounts),
    avg_expense_temp=safe_mean(pw.this.all_expense_amounts),
    std_income_temp=safe_std(pw.this.all_income_amounts),
    std_expense_temp=safe_std(pw.this.all_expense_amounts),
    balance_avg_temp=safe_mean(pw.this.all_balances),
    balance_std_temp=safe_std(pw.this.all_balances),
    avg_amount_temp=safe_mean(pw.this.all_amounts),
)

# Compute final behavioral metrics with loan recommendations
final_features = features.select(
    customer_id=pw.this.customer_id,
    
    # === Transaction Counts (Features 1-3) ===
    total_transactions=pw.this.total_transactions,
    num_income=pw.this.num_income,
    num_expense=pw.this.num_expense,
    
    # === Amount Aggregates (Features 4-9) ===
    total_income=pw.this.total_income,
    total_expense=pw.this.total_expense,
    avg_income=pw.this.avg_income,
    avg_expense=pw.this.avg_expense,
    median_income=pw.this.median_income,
    median_expense=pw.this.median_expense,
    
    # === Statistical Measures (Features 10-13) ===
    std_income=pw.this.std_income,
    std_expense=pw.this.std_expense,
    max_income=pw.this.max_income,
    max_expense=pw.this.max_expense,
    
    # === Balance Analytics (Features 14-18) ===
    balance_current=pw.this.balance_current,
    balance_avg=pw.this.balance_avg,
    balance_min=pw.this.balance_min,
    balance_max=pw.this.balance_max,
    balance_volatility=pw.this.balance_std_temp / (pw.this.balance_avg_temp + 1.0),
    
    # === Behavioral Metrics (Features 19-25) ===
    net_cashflow=pw.this.total_income - pw.this.total_expense,
    income_expense_ratio=pw.this.total_income / (pw.this.total_expense + 1.0),
    avg_transaction_size=pw.this.avg_amount_temp,
    transaction_frequency=pw.cast(float, pw.this.total_transactions) / 
                          (pw.cast(float, pw.this.last_transaction_time - pw.this.first_transaction_time) / 86400.0 + 1.0),
    income_consistency=pw.this.avg_income_temp / (pw.this.std_income_temp + 1.0),
    expense_consistency=pw.this.avg_expense_temp / (pw.this.std_expense_temp + 1.0),
    spending_rate=pw.this.total_expense / (pw.this.total_income + 1.0),
    
    # === Category Diversity (Features 26-28) ===
    unique_categories=pw.this.unique_categories,
    primary_category=pw.this.primary_category,
    category_concentration=pw.this.category_concentration,
    
    # === Temporal (Features 29-30) ===
    first_transaction_time=pw.this.first_transaction_time,
    last_transaction_time=pw.this.last_transaction_time,
    
    # === Loan Recommendation ===
    loan_recommendation=check_loan_recommendation(
        pw.this.customer_id,
        pw.this.total_transactions,
        pw.this.num_income,
        pw.this.num_expense,
        pw.this.total_income,
        pw.this.total_expense,
        pw.this.avg_income,
        pw.this.avg_expense,
        pw.this.median_income,
        pw.this.median_expense,
        pw.this.std_income,
        pw.this.std_expense,
        pw.this.max_income,
        pw.this.max_expense,
        pw.this.balance_current,
        pw.this.balance_avg,
        pw.this.balance_min,
        pw.this.balance_max,
        pw.this.balance_std_temp / (pw.this.balance_avg_temp + 1.0),
        pw.this.total_income - pw.this.total_expense,
        pw.this.total_income / (pw.this.total_expense + 1.0),
        pw.this.avg_amount_temp,
        pw.cast(float, pw.this.total_transactions) / 
            (pw.cast(float, pw.this.last_transaction_time - pw.this.first_transaction_time) / 86400.0 + 1.0),
        pw.this.avg_income_temp / (pw.this.std_income_temp + 1.0),
        pw.this.avg_expense_temp / (pw.this.std_expense_temp + 1.0),
        pw.this.total_expense / (pw.this.total_income + 1.0),
        pw.this.unique_categories,
        pw.this.category_concentration,
    ),
)

print("✓ Feature computation pipeline configured\n")

# ==================== OUTPUT ====================

print("[3/3] Configuring outputs...")

# Write to NATS for downstream consumers
pw.io.nats.write(
    final_features,
    NATS_URL,
    topic=FEATURES_TOPIC,
    format="json",
)

# Write to CSV for persistence and analysis
pw.io.csv.write(final_features, "output/customer_features_live.csv")

# Also output transaction summary
transaction_summary = transactions.groupby(pw.this.customer_id).reduce(
    customer_id=pw.this.customer_id,
    latest_trans_id=pw.reducers.max(pw.this.trans_id),
    latest_timestamp=pw.reducers.max(pw.this.timestamp),
    latest_amount=pw.reducers.any(pw.this.amount),
    latest_type=pw.reducers.any(pw.this.trans_type),
    latest_category=pw.reducers.any(pw.this.category),
    transaction_count=pw.reducers.count(),
)

pw.io.csv.write(transaction_summary, "output/transaction_updates.csv")

print("✓ Outputs configured")
print("  - NATS topic: features.customer")
print("  - CSV file: output/customer_features_live.csv")
print("  - CSV file: output/transaction_updates.csv")
print("  - CSV file: output/loan_recommendations.csv (📋 LOAN RECOMMENDATIONS)")

# ==================== RUN PIPELINE ====================

print("\n" + "=" * 70)
print("Pipeline ready! Waiting for transactions...")
print("=" * 70)
print("\nTo publish a transaction, use:")
print(f'  nats pub {TRANSACTION_TOPIC} \'{{"trans_id":554,"customer_id":239,"timestamp":1737291234,"trans_type":"EXPENSE","category":"Groceries","amount":5000.0,"balance":15000.0}}\'')
print("\nOr run: python publish_transactions.py")
print("\n📋 Loan recommendations will be written to: output/loan_recommendations.csv")
print("\nPress Ctrl+C to stop")
print("=" * 70 + "\n")

pw.run()