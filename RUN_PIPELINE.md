# How to Run the Pathway Data Pipeline

## Quick Start (3 Steps)

### Step 1: Verify Setup
```bash
python test_data_fetch.py
```

Expected output:
```
================================================================================
DATA_FETCH.PY TEST SCRIPT
================================================================================

1. Checking Pathway installation...
   ✓ Pathway 0.x.x is installed
   ✓ License key configured

2. Checking data directories...
   ✓ data/present_tables exists
   ✓ data/pathway_output created/exists

3. Checking CSV files in present_tables...
   ✓ client.csv             (5,369 rows)
   ✓ account.csv            (4,500 rows)
   ...

✓ All checks passed!
```

### Step 2: Test Minimal Pipeline (Optional)
```bash
python test_pathway_minimal.py
```

This runs a 5-second test to verify everything works.

### Step 3: Run Full Pipeline
```bash
# Option A: Using Python directly
python data_fetch.py

# Option B: Using the shell script (recommended)
./run_data_fetch.sh
```

## What the Pipeline Does

```
┌─────────────────────────────────────┐
│ Input: data/present_tables/         │
│   ├── client.csv                    │
│   ├── account.csv                   │
│   ├── disp.csv                      │
│   ├── trans.csv                     │
│   ├── loan.csv                      │
│   ├── order.csv                     │
│   ├── card.csv                      │
│   └── district.csv                  │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ Pathway Processing                  │
│   • Streams CSV files               │
│   • Converts CZK → USD              │
│   • Aggregates transactions         │
│   • Joins multiple tables           │
│   • Calculates features             │
│   • Updates continuously            │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ Output: data/pathway_output/        │
│   ├── master_table.csv              │
│   ├── transaction_stats.csv         │
│   ├── loan_stats.csv                │
│   ├── client_features.csv           │
│   └── master_summary.jsonl          │
└─────────────────────────────────────┘
```

## Features Calculated

### Transaction Features (per account → per client)
- `total_transactions`, `num_incoming`, `num_outgoing`
- `total_incoming`, `total_outgoing`, `avg_incoming`, `avg_outgoing`
- `balance_min`, `balance_max`, `balance_mean`
- `net_cashflow`, `incoming_outgoing_ratio`
- `avg_transaction_amount`, `transaction_frequency`
- `unique_k_symbols`, `unique_operations`, `unique_banks`
- `first_transaction_date`, `last_transaction_date`

### Loan Features (per account → per client)
- `num_loans`
- `loan_amount_total_usd`, `loan_amount_avg_usd`
- `loan_duration_avg`, `loan_payment_avg_usd`
- `first_loan_date`, `last_loan_date`
- `loan_status`

### Order Features (per account → per client)
- `num_orders`
- `total_order_amount_usd`, `avg_order_amount_usd`
- `unique_banks_orders`

### Card Features (per client)
- `num_cards`
- `earliest_card_issue`

### District Features
- `A1` through `A11` (demographic and economic data)

## Monitoring the Pipeline

### Watch Master Table Growth
```bash
# In a separate terminal
watch -n 1 'wc -l data/pathway_output/master_table.csv'
```

### View Real-Time JSON Stream
```bash
tail -f data/pathway_output/master_summary.jsonl
```

### Check All Outputs
```bash
ls -lh data/pathway_output/
```

## Combining with Publishers

For a complete streaming workflow:

### Terminal 1: Start Pathway Processing
```bash
python data_fetch.py
```

### Terminal 2: Stream New Data
```bash
# Stream all tables continuously
python publishers/stream_all.py

# Or stream in controlled batches
python publishers/stream_all.py --mode single
```

Data flow:
```
stream_tables → (publishers) → present_tables → (pathway) → pathway_output
```

## Output Files Explained

### master_table.csv
Complete client-level feature table with:
- Client demographics (client_id, birth_number, district_id)
- Transaction aggregations
- Loan metrics
- Order summaries
- Card information
- District data

**Use for:** ML model training, customer analytics, dashboards

### transaction_stats.csv
Account-level transaction metrics before client aggregation.

**Use for:** Account-level analysis, debugging

### loan_stats.csv
Account-level loan metrics before client aggregation.

**Use for:** Loan portfolio analysis

### client_features.csv
Client-level aggregated features without district/card joins.

**Use for:** Feature engineering, intermediate analysis

### master_summary.jsonl
Real-time JSON Lines stream with key metrics.

**Use for:** Real-time monitoring, streaming analytics

**Format:**
```json
{"client_id":"1","num_accounts":2,"balance_mean":1234.56,"total_incoming":10000.0,"total_outgoing":8000.0,"net_cashflow":2000.0}
```

## Stopping the Pipeline

Press **Ctrl+C** to gracefully stop the pipeline.

Expected output:
```
^C
================================================================================
Pipeline stopped
End time: 2025-11-15 05:30:00
================================================================================
```

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'pathway'"

**Solution:**
```bash
pip install pathway
```

### Problem: "FileNotFoundError: data/present_tables/client.csv"

**Solution:**
1. Check if files exist: `ls data/present_tables/`
2. Run data preprocessing: `python data_preprocessing/split_data.py`
3. Or use publishers to populate: `python publishers/stream_all.py --mode single`

### Problem: Pipeline starts but no output

**Solution:**
1. Check if present_tables has data: `wc -l data/present_tables/*.csv`
2. Wait a few seconds - initial processing takes time
3. Check output directory: `ls data/pathway_output/`

### Problem: "TypeError: Got unexpected keyword arguments"

**Solution:** This is fixed in the current version. Make sure you're running the latest `data_fetch.py`.

### Problem: High memory usage

**Solution:**
1. Reduce autocommit frequency in data_fetch.py:
   ```python
   autocommit_duration_ms=5000  # Change from 1000 to 5000
   ```
2. Process smaller batches with publishers

### Problem: Pipeline runs but outputs are empty

**Solution:**
1. Check if source files have data (not just headers)
2. Verify CSV format is correct
3. Run the minimal test: `python test_pathway_minimal.py`

## Performance Tips

### Small Datasets (< 10K rows)
- Use default settings
- Real-time latency: < 1 second

### Medium Datasets (10K-100K rows)
- Consider increasing autocommit duration to 2-3 seconds
- Expected latency: 1-3 seconds

### Large Datasets (> 100K rows)
- Increase autocommit duration to 5-10 seconds
- Process in batches using publishers
- Expected latency: 3-10 seconds

## Configuration Options

### Change Autocommit Duration
Edit `data_fetch.py`:
```python
# Line ~128 (and similar for other tables)
client_table = pw.io.csv.read(
    f"{PRESENT_TABLES_PATH}/client.csv",
    schema=ClientSchema,
    mode="streaming",
    autocommit_duration_ms=5000  # Change this value (in milliseconds)
)
```

### Change Currency Conversion Rate
Edit `data_fetch.py`:
```python
# Line ~17
CZK_TO_USD = 0.038  # Change this value
```

### Disable Specific Outputs
Comment out unwanted outputs in `data_fetch.py` (lines ~420-436):
```python
# pw.io.csv.write(trans_stats, f"{OUTPUT_PATH}/transaction_stats.csv")  # Commented out
```

## Advanced Usage

### Use with ML Pipeline
```python
import pandas as pd

# Read continuously updated master table
df = pd.read_csv('data/pathway_output/master_table.csv')

# Use for predictions
X = df[feature_columns]
y_pred = model.predict(X)
```

### Stream to Database
Modify `data_fetch.py` to add PostgreSQL output:
```python
# Add at the end before pw.run()
pw.io.postgres.write(
    master_table,
    host="localhost",
    port=5432,
    database="banking",
    table_name="client_features"
)
```

### Real-Time Alerts
Add filtering before output:
```python
# High-risk clients
high_risk = master_table.filter(
    (pw.this.net_cashflow < 0) &
    (pw.this.num_loans > 2)
)

pw.io.jsonlines.write(high_risk, f"{OUTPUT_PATH}/high_risk_alerts.jsonl")
```

## Next Steps

1. ✅ Run `python test_data_fetch.py` to verify setup
2. ✅ Run `python test_pathway_minimal.py` for a quick test
3. ✅ Run `python data_fetch.py` to start the full pipeline
4. ✅ Monitor outputs in `data/pathway_output/`
5. ✅ Integrate with your ML workflow
6. ✅ Set up continuous streaming with publishers

## Support

- **Test script:** `python test_data_fetch.py`
- **Minimal test:** `python test_pathway_minimal.py`
- **Documentation:** [DATA_FETCH_README.md](DATA_FETCH_README.md)
- **Quick start:** [QUICKSTART_PATHWAY.md](QUICKSTART_PATHWAY.md)
- **Publishers:** [publishers/README.md](publishers/README.md)

## Files Summary

| File | Purpose |
|------|---------|
| `data_fetch.py` | Main pipeline script |
| `test_data_fetch.py` | Comprehensive setup verification |
| `test_pathway_minimal.py` | Quick 5-second functionality test |
| `run_data_fetch.sh` | Shell script to run pipeline with checks |
| `RUN_PIPELINE.md` | This file - complete running guide |
| `DATA_FETCH_README.md` | Detailed technical documentation |
| `QUICKSTART_PATHWAY.md` | Quick reference guide |
