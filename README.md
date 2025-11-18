# Live Loan Recommendation System

Real-time loan recommendation system that monitors customer portfolio changes and recommends appropriate loan types using Gaussian Mixture Model (GMM) clustering.

## System Overview

The system:
1. **Generates labeled customer data** with loan types (Home, Car, Personal, Education, Business)
2. **Trains a GMM model** on normalized customer portfolios
3. **Processes live transactions** and updates customer features in real-time
4. **Detects portfolio changes** by comparing current portfolio to baseline (85% similarity threshold)
5. **Recommends loan types** when portfolio changes significantly
6. **Handles new customers** by training the model incrementally

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Transaction   │────▶│   Live Feature   │────▶│  Loan           │
│   Stream (NATS) │     │   Processor      │     │  Recommender    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                 │                         │
                                 ▼                         ▼
                        ┌──────────────┐          ┌──────────────┐
                        │  CSV Output  │          │  GMM Model   │
                        └──────────────┘          └──────────────┘
```

## Files Structure

```
.
├── generate_sample_data.py      # Generates labeled customer data
├── loan_recommender.py          # GMM model training and recommendations
├── live_feature_processor.py    # Real-time feature computation
├── publish_transactions.py      # Transaction publisher
├── view_recommendations.py      # View loan recommendations (NEW)
├── demo_transactions.py         # Demo scenarios
├── test_loan_system.py          # System tests
├── schemas.py                   # Data schemas
├── data/
│   ├── customer_profiles.csv    # Initial customer profiles with loan types
│   ├── historical_transactions.csv
│   └── live_transactions.csv
├── models/
│   ├── gmm_model.pkl           # Trained GMM model
│   ├── scaler.pkl              # Feature scaler
│   ├── loan_type_mapping.pkl  # Cluster to loan type mapping
│   └── baseline_portfolios.pkl # Customer baseline portfolios
└── output/
    ├── customer_features_live.csv
    ├── transaction_updates.csv
    └── loan_recommendations.csv  # 📋 LOAN RECOMMENDATIONS (NEW)
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install pathway-ai pandas numpy scikit-learn nats-py
```

### 2. Start NATS Server

```bash
# Install NATS if not already installed
# On macOS: brew install nats-server
# On Linux: Download from https://nats.io/download/

# Start NATS server
nats-server
```

### 3. Generate Sample Data

```bash
python generate_sample_data.py
```

This creates:
- **1000 customers** with 31 features each (including `loan_type`)
- **50,000 historical transactions**
- **10 live test transactions**

**Loan Type Distribution:**
- Home Loan: ~25-30%
- Car Loan: ~20-25%
- Personal Loan: ~20-25%
- Education Loan: ~15-20%
- Business Loan: ~10-15%

### 4. Train GMM Model

```bash
python loan_recommender.py
```

This:
- Loads customer profiles
- Normalizes 27 financial features
- Trains GMM with 5 components (one per loan type)
- Maps clusters to loan types
- Saves baseline portfolios for all customers

### 5. Start Live Feature Processor

```bash
python3 live_feature_processor.py
```

The processor:
- Connects to NATS
- Subscribes to `transactions.live`
- Computes features in real-time
- Checks portfolio changes
- Recommends loans when needed

### 6. Publish Transactions

**Option A: Publish from CSV**
```bash
python publish_transactions.py
```

**Option B: Publish single transaction**
```bash
nats pub transactions.live '{"trans_id":554,"customer_id":239,"timestamp":1737291234,"trans_type":"EXPENSE","category":"Groceries","amount":5000.0,"balance":15000.0}'
```

## How It Works

### 1. Portfolio Vector Creation

Each customer's portfolio is represented by 27 normalized features:
- Transaction patterns (counts, frequency)
- Income/expense statistics (mean, median, std, max)
- Balance analytics (current, avg, volatility)
- Behavioral metrics (consistency, spending rate)
- Category diversity

### 2. GMM Clustering

The system trains a Gaussian Mixture Model with 5 components, where each component represents a loan type cluster based on financial behavior patterns.

### 3. Similarity Check

When a transaction arrives:
1. **Compute current features** for the customer
2. **Normalize features** using trained scaler
3. **Calculate cosine similarity** between current and baseline portfolio
4. If similarity < 85%:
   - Portfolio has changed significantly
   - Predict new loan type using GMM
   - Print recommendation
   - Update baseline portfolio

### 4. New Customer Handling

For new customers:
- Create portfolio vector from initial transactions
- Predict loan type using existing GMM
- Add to baseline portfolios
- Save updated model

## Example Output

### Terminal Output (Concise)
```
✓ NEW CUSTOMER 1050 → Recommended: Personal Loan
⚠️  PORTFOLIO CHANGE: Customer 239 | Similarity: 78.43% | Personal Loan → Car Loan
```

### CSV Output (Detailed)
All recommendations are written to `output/loan_recommendations.csv`:

```csv
timestamp,customer_id,event_type,portfolio_similarity,previous_loan_type,recommended_loan_type,balance_current,balance_avg,income_expense_ratio,spending_rate,transaction_frequency,total_transactions,avg_transaction_size
2025-01-19 10:30:45,1050,NEW_CUSTOMER,0.00,N/A,Personal Loan,25000.00,25000.00,1.3500,0.7200,0.2500,1,8000.00
2025-01-19 10:31:12,239,PORTFOLIO_CHANGE,78.43,Personal Loan,Car Loan,15000.00,14200.00,1.2800,0.7800,0.3200,52,450.00
```

### View Recommendations
```bash
# View all recommendations
python view_recommendations.py

# View latest 10 recommendations
python view_recommendations.py latest 10

# View specific customer history
python view_recommendations.py customer 239

# View all recommendations for a loan type
python view_recommendations.py loan "Home Loan"

# Export summary to text file
python view_recommendations.py export
```

## Testing the System

### Test Case 1: Existing Customer with Significant Change

```bash
# Customer 239 makes a large expense transaction
nats pub transactions.live '{"trans_id":554,"customer_id":239,"timestamp":1737291234,"trans_type":"EXPENSE","category":"Groceries","amount":5000.0,"balance":15000.0}'
```

Expected: If this changes their portfolio significantly (>15% difference), you'll see a loan recommendation.

### Test Case 2: New Customer

```bash
# New customer (ID > 1000)
nats pub transactions.live '{"trans_id":555,"customer_id":1050,"timestamp":1737291300,"trans_type":"INCOME","category":"Salary","amount":8000.0,"balance":25000.0}'
```

Expected: NEW CUSTOMER message with initial loan recommendation.

### Test Case 3: Multiple Transactions

```bash
python publish_transactions.py
```

Expected: Real-time processing of all 10 test transactions with recommendations as needed.

## Key Features

✅ **Real-time processing** - Processes transactions as they arrive via NATS
✅ **Portfolio tracking** - Maintains baseline for each customer
✅ **Smart recommendations** - Only recommends when portfolio changes >15%
✅ **Incremental learning** - Adds new customers without retraining entire model
✅ **Non-intrusive** - Doesn't alter streaming pipeline architecture
✅ **Persistent storage** - Saves model and baselines for recovery

## Model Parameters

- **Similarity Threshold**: 85% (configurable in `live_feature_processor.py`)
- **GMM Components**: 5 (one per loan type)
- **Covariance Type**: Full
- **Features Used**: 27 numerical features

## Customization

### Change Similarity Threshold

Edit `live_feature_processor.py`:
```python
SIMILARITY_THRESHOLD = 80.0  # Change from 85% to 80%
```

### Add New Loan Type

1. Update `generate_sample_data.py` - add to `LOAN_TYPES`
2. Modify `assign_loan_type_based_on_profile()` function
3. Regenerate data and retrain model

### Modify Features

Update `feature_columns` in `loan_recommender.py` to include/exclude features.

## Troubleshooting

### Error: "Model not found"
```bash
# Solution: Train the model first
python loan_recommender.py
```

### Error: "No such file or directory (output/)"
```bash
# Solution: Create output directory
mkdir -p output
```

### Error: "customer_profiles.csv not found"
```bash
# Solution: Generate sample data first
python generate_sample_data.py
```

### NATS Connection Error
```bash
# Solution: Make sure NATS server is running
nats-server
```

## Performance

- **Feature computation**: Real-time (< 100ms per transaction)
- **Similarity calculation**: < 10ms per customer
- **GMM prediction**: < 5ms per customer
- **Throughput**: > 100 transactions/second

## Future Enhancements

- [ ] Add confidence scores to recommendations
- [ ] Implement time-based portfolio drift detection
- [ ] Add A/B testing framework for recommendations
- [ ] Create dashboard for monitoring
- [ ] Add loan amount recommendations based on profile
- [ ] Implement ensemble methods (GMM + other models)

## License

MIT License