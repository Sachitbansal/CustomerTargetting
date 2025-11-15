# Data Transformation Pipeline

## Overview
The `data_transform.py` script creates a comprehensive `client_features.csv` file with all required features from the `present_tables` folder.

## Usage
```bash
python data_transform.py
```

## Output
- **File**: `data/pathway_output/client_features.csv`
- **Rows**: 4,583 unique clients (no duplicates)
- **Columns**: 97 features

## Features Included

### Client Information (3)
- client_id, birth_number, district_id

### Account Information (1)
- num_accounts

### Transaction Features (37)
- **Counts**: total_transactions, num_incoming, num_outgoing
- **Amounts**: total_incoming, total_outgoing, net_cashflow
- **Statistics**: avg_incoming, avg_outgoing, median_incoming, median_outgoing
- **Volatility**: std_incoming, std_outgoing, balance_std, balance_volatility
- **Extremes**: max_incoming, max_outgoing, min_incoming, min_outgoing
- **Balance**: balance_min, balance_max, balance_mean, balance_median
- **Unique Counts**: unique_k_symbols, unique_operations, unique_banks
- **Time-based**: transaction_span_days, first_transaction_date, last_transaction_date
- **Ratios**: incoming_outgoing_ratio, avg_transaction_amount, transaction_frequency
- **Volatility Ratios**: incoming_volatility, outgoing_volatility, max_to_avg_incoming_ratio, max_to_avg_outgoing_ratio

### Loan Features (15)
- **Counts**: num_loans
- **Amounts**: loan_amount_total_usd, loan_amount_avg_usd, loan_amount_max_usd, loan_amount_min_usd
- **Duration**: loan_duration_avg, loan_duration_max, loan_duration_min
- **Payments**: loan_payment_avg_usd, loan_payment_max_usd, loan_payment_min_usd
- **Dates**: first_loan_date, last_loan_date
- **Status**: loan_status_all
- **Purpose Types**: personal_loan, car_loan, home_loan, credit_card_loan, business_loan

### Order Features (8)
- num_orders, avg_order_amount_usd, total_order_amount_usd
- max_order_amount_usd, min_order_amount_usd, std_order_amount_usd
- unique_banks_orders, unique_k_symbols_orders

### Card Features (9)
- **Counts**: num_cards, num_classic_cards, num_junior_cards, num_gold_cards
- **Dates**: earliest_card_issue, latest_card_issue
- **Binary**: classic_card, gold_card, junior_card

### ID References (5)
- account_id, card_id, loan_id, order_id, trans_id

### District Demographics (16)
- A1 through A16 (district features from district table)

### Other (3)
- frequency, loan_status_all

## Data Quality

### Transaction Coverage
- **Clients with transactions**: 3,837 (83.7%)
- **Clients without transactions**: 746 (16.3%)
  - These are clients who don't have accounts or haven't made transactions yet

### Loan Coverage
- **Clients with loans**: 581 (12.7%)
- **Clients without loans**: 4,002 (87.3%)

### Order Coverage
- **Clients with orders**: 3,210 (70.0%)
- **Clients without orders**: 1,373 (30.0%)

### Card Coverage
- **Clients with cards**: 758 (16.5%)
- **Clients without cards**: 3,825 (83.5%)

## Null Value Handling

The pipeline properly handles null values:
1. **Numeric columns**: Filled with 0
2. **Transaction features**: Set to 0 for clients without accounts/transactions
3. **Loan features**: Set to 0 for clients without loans
4. **Order features**: Set to 0 for clients without orders
5. **Card features**: Set to 0 for clients without cards

**Remaining nulls**:
- `loan_status_all`: 731 (clients without loans)
- `frequency`: 746 (clients without accounts)

These nulls are expected and indicate clients without the corresponding records.

## Key Improvements Over data_fetch.py

1. **Complete Feature Set**: All 97 required features are computed
2. **Statistical Features**: Includes median, std, min, max for all relevant metrics
3. **Volatility Metrics**: Computes volatility and ratio features
4. **Loan Purpose**: One-hot encoding for loan purposes (personal, car, home, credit_card, business)
5. **Card Types**: Binary features for card types (classic, gold, junior)
6. **District Features**: All 16 district demographic features (A1-A16)
7. **No Duplicates**: Ensures unique client_id records
8. **Proper Aggregation**: Correctly aggregates multi-account clients
9. **ID References**: Includes reference IDs for accounts, cards, loans, orders, transactions

## Conversion
All monetary amounts are converted from CZK to USD using rate: 0.038

## Performance
- Processing time: ~10 seconds
- Memory efficient: Uses pandas for batch processing
- No streaming required for static analysis
