# Complete Step-by-Step Pipeline Execution Guide

## Prerequisites Setup

Before running the pipeline, ensure you have:

```bash
# 1. Check Python version (should be 3.8+)
python --version

# 2. Install/verify required packages
pip install pandas numpy faker scikit-learn pathway python-dateutil matplotlib pillow iterstrat

# 3. Start NATS server (required for streaming)
# Install NATS first if not present: brew install nats-server (macOS) or apt-get install nats-server (Linux)
nats-server &

# 4. Verify NATS is running
nats-sub ">" &  # Subscribe to all topics (background)
```

---

## Phase 1: Data Generation & Preparation (Sequential)

### Step 1: Generate Synthetic Dataset
```bash
cd /home/shinchan/Projects/TargettedCalling

# Generate 12,500 customers and their 4 months of transaction history
python experiment7/generate_dataset.py
```

**Expected Output:**
- `customers_master_multi_product.csv` (12,500 customers with features)
- `transactions_history_categorized.csv` (multiple transactions per customer)
- Console logs showing progress and customer archetype distribution

**Verification:**
```bash
# Check generated files
wc -l customers_master_multi_product.csv transactions_history_categorized.csv

# Check first few rows
head -3 customers_master_multi_product.csv | cut -d',' -f1-5
head -3 transactions_history_categorized.csv
```

---

### Step 2: Split Data into Train & Stream Sets
```bash
cd /home/shinchan/Projects/TargettedCalling

# Perform stratified split: 10,000 train + 2,500 streaming
python experiment7/split_data.py
```

**Expected Output:**
- `initial_training_data.csv` (10,000 customers)
- `streaming_customers_initial_state.csv` (2,500 customers)
- `streaming_transactions.csv` (transactions for streaming customers only)
- Console logs showing stratification verification

**Verification:**
```bash
# Verify file sizes
wc -l initial_training_data.csv streaming_customers_initial_state.csv streaming_transactions.csv

# Check target column ratios are balanced
python -c "
import pandas as pd
df_train = pd.read_csv('initial_training_data.csv')
df_stream = pd.read_csv('streaming_customers_initial_state.csv')
targets = ['opted_home_loan', 'opted_car_loan', 'recommend_nifty50', 'recommend_elss']
for col in targets:
    print(f'{col}: Train={df_train[col].mean():.3f}, Stream={df_stream[col].mean():.3f}')
"
```

---

### Step 3: Create Master File
```bash
cd /home/shinchan/Projects/TargettedCalling

# Combine training and streaming data into single master file
python experiment7/create_masterfile.py
```

**Expected Output:**
- `MASTERFILE.csv` (10,000 + 2,500 = 12,500 customers)
- Target columns set to 0 for streaming customers
- Console logs showing merge process

**Verification:**
```bash
# Check MASTERFILE was created
wc -l MASTERFILE.csv

# Verify target columns are 0 for streaming customers
python -c "
import pandas as pd
df = pd.read_csv('MASTERFILE.csv')
print(f'Total customers: {len(df)}')
print(f'Columns: {df.shape[1]}')
print(f'Sample customer IDs: {df[\"customer_id\"].head(3).tolist()}')
"
```

---

### Step 4: Add Streaming Columns
```bash
cd /home/shinchan/Projects/TargettedCalling

# Add tracking columns for streaming operations
python add_streaming_columns.py
```

**Expected Output:**
- Updated `MASTERFILE.csv` with streaming columns
- `last_update_timestamp` initialized to '1970-01-01T00:00:00'
- Console logs showing columns added

**Verification:**
```bash
# Check streaming columns were added
python -c "
import pandas as pd
df = pd.read_csv('MASTERFILE.csv')
cols = df.columns.tolist()
streaming_cols = [c for c in cols if 'stream' in c.lower() or 'reach' in c.lower()]
print(f'Streaming columns: {streaming_cols}')
"
```

---

### Step 5: Sort Transactions Chronologically
```bash
cd /home/shinchan/Projects/TargettedCalling

# Sort transactions by datetime for proper event-driven simulation
python sort_transactions.py
```

**Expected Output:**
- Sorted `streaming_transactions.csv`
- Console logs showing sort completion
- Verified transactions are ordered by `txn_datetime`

**Verification:**
```bash
# Check transactions are sorted
python -c "
import pandas as pd
df = pd.read_csv('streaming_transactions.csv', parse_dates=['txn_datetime'])
print(f'Total transactions: {len(df)}')
print(f'Date range: {df[\"txn_datetime\"].min()} to {df[\"txn_datetime\"].max()}')
print(f'Is sorted: {df[\"txn_datetime\"].is_monotonic_increasing}')
print(f'Sample times:\n{df[\"txn_datetime\"].head(3)}')
"
```

---

## Phase 2: Machine Learning Model Training (Parallel - Can run in background)

### Step 6A: Train Home Loan Model
```bash
cd /home/shinchan/Projects/TargettedCalling

# In terminal 1 (run in background)
python experiment7/run_simulation_home_loan.py &
```

**Expected Output:**
- Trained GMM and Neural Network models
- `home_loan_simulation.gif` visualization
- Model performance metrics
- Console logs showing training progress

---

### Step 6B: Train Car Loan Model
```bash
cd /home/shinchan/Projects/TargettedCalling

# In terminal 2 (run in background)
python experiment7/run_simulation_car_loan.py &
```

**Expected Output:**
- Trained models for car loan recommendation
- `car_loan_simulation.gif` visualization

---

### Step 6C: Train Nifty50 Model
```bash
cd /home/shinchan/Projects/TargettedCalling

# In terminal 3 (run in background)
python experiment7/run_simulation_nifty50.py &
```

**Expected Output:**
- Trained models for Nifty50 recommendation
- `nifty50_simulation.gif` visualization

---

### Step 6D: Train ELSS Model
```bash
cd /home/shinchan/Projects/TargettedCalling

# In terminal 4 (run in background)
python experiment7/run_simulation_elss.py &
```

**Expected Output:**
- Trained models for ELSS recommendation
- `elss_simulation.gif` visualization

**Wait for all models to complete:**
```bash
# Monitor background jobs
jobs -l

# Wait for all to finish
wait
```

---

## Phase 3: Real-Time Streaming Pipeline (3 Terminals - Parallel)

Once Phase 1 is complete, you can start the streaming pipeline. This requires 3 terminal windows running simultaneously.

### Prerequisites for Streaming Phase:
```bash
# Verify NATS is running
ps aux | grep nats-server

# If not running, start it
nats-server &

# Wait a moment for NATS to start
sleep 2
```

---

### Step 7: Terminal 1 - Start Transaction Publisher
```bash
# TERMINAL 1
cd /home/shinchan/Projects/TargettedCalling

# Streams transactions to NATS at 20 TPS (transactions per second)
python transactionPublisher/run_publisher.py
```

**Expected Output:**
```
Loading CSV: streaming_transactions.csv
Streaming 12500 rows at 20 TPS → ./transactionPublisher/temp_stream.csv
[STREAM] wrote 100 rows
[STREAM] wrote 200 rows
...
```

**Notes:**
- This will continuously stream transactions indefinitely
- Press Ctrl+C to stop
- Default: 20 TPS (configurable in code)

---

### Step 8: Terminal 2 - Start Enrichment Node
```bash
# TERMINAL 2
cd /home/shinchan/Projects/TargettedCalling

# Reads transactions and updates customer profiles in real-time
python MASTERFILENode/run_enrichment_node.py
```

**Expected Output:**
```
═══════════════════════════════════════════════
        CUSTOMER 360 ENRICHMENT NODE           
═══════════════════════════════════════════════
✓ Initialized state with 12500 customers from 'MASTERFILE.csv'
✓ Listening for transactions on NATS topic 'transactions.stream'
✓ Update logic is configured. Ready to process transactions.
✓ Will write updated customer profiles to './MASTERFILENode/temp_MASTERFILE_stream.csv'
```

**Notes:**
- Enrichment happens in real-time as transactions arrive
- Press Ctrl+C to stop
- Creates/updates `temp_MASTERFILE_stream.csv` with customer profile changes

---

### Step 9: Terminal 3 - Start Lead Dispatcher Node
```bash
# TERMINAL 3
cd /home/shinchan/Projects/TargettedCalling

# Applies business rules and publishes qualified leads
python MASTERFILENode/run_dispatcher_node.py
```

**Expected Output:**
```
═══════════════════════════════════════════════
        LEAD DISPATCHER NODE                   
═══════════════════════════════════════════════
✓ Listening for updated customer profiles from './MASTERFILENode/temp_MASTERFILE_stream.csv'
✓ Home Loan lead rule configured (vol > 100000, cooldown: 90 days)
✓ Car Loan lead rule configured (vol > 50000, cooldown: 45 days)
✓ Nifty50 lead rule configured (vol > 25000, cooldown: 30 days)
✓ ELSS lead rule configured (vol > 40000, cooldown: 60 days)

✓ Publishing configured for all lead streams.
```

**Notes:**
- Monitors updated customer profiles in real-time
- Publishes qualified leads to NATS topics
- Press Ctrl+C to stop

---

## Phase 4: Real-Time Monitoring (Optional)

### Step 10: Monitor NATS Topics (Optional Terminal)
```bash
# TERMINAL 4 (optional - for monitoring)

# Subscribe to all lead topics
nats-sub "leads.>" --server=nats://localhost:4222

# Or monitor specific topics:
nats-sub "leads.checkHomeLoan" --server=nats://localhost:4222
nats-sub "leads.checkCarLoan" --server=nats://localhost:4222
nats-sub "leads.checkNifty50" --server=nats://localhost:4222
nats-sub "leads.checkElss" --server=nats://localhost:4222
```

**Expected Output:**
```
Subscribing on [leads.checkHomeLoan]
[#1] Received on [leads.checkHomeLoan]:
{"customer_id":"CUST_005234","final_credit_score":765.5,...}

[#2] Received on [leads.checkHomeLoan]:
{"customer_id":"CUST_008901","final_credit_score":780.2,...}
```

---

## Complete Pipeline Commands Summary

### All-in-One Quick Start (Sequential then Parallel)

```bash
#!/bin/bash
cd /home/shinchan/Projects/TargettedCalling

# Phase 1: Data Generation & Preparation
echo "=== Phase 1: Data Generation ==="
python experiment7/generate_dataset.py && echo "✓ Dataset generated"

echo "=== Phase 2: Data Splitting ==="
python experiment7/split_data.py && echo "✓ Data split complete"

echo "=== Phase 3: Create Master File ==="
python experiment7/create_masterfile.py && echo "✓ Master file created"

echo "=== Phase 4: Add Streaming Columns ==="
python add_streaming_columns.py && echo "✓ Streaming columns added"

echo "=== Phase 5: Sort Transactions ==="
python sort_transactions.py && echo "✓ Transactions sorted"

# Ensure NATS is running
echo "=== Starting NATS Server ==="
nats-server &
sleep 2

# Phase 2: Start ML Training in Background
echo "=== Phase 6: ML Model Training (background) ==="
python experiment7/run_simulation_home_loan.py &
python experiment7/run_simulation_car_loan.py &
python experiment7/run_simulation_nifty50.py &
python experiment7/run_simulation_elss.py &

# Phase 3: Start Streaming Pipeline
echo "=== Phase 7: Streaming Pipeline ==="
# Open 3 new terminals for:
# Terminal 1: python transactionPublisher/run_publisher.py
# Terminal 2: python MASTERFILENode/run_enrichment_node.py
# Terminal 3: python MASTERFILENode/run_dispatcher_node.py

echo ""
echo "✓ Initialization complete!"
echo "Now open 3 new terminals and run:"
echo "  Terminal 1: python transactionPublisher/run_publisher.py"
echo "  Terminal 2: python MASTERFILENode/run_enrichment_node.py"
echo "  Terminal 3: python MASTERFILENode/run_dispatcher_node.py"
```

---

## Testing Checklist

### Phase 1 Verification
- [ ] `customers_master_multi_product.csv` created with 12,500+ rows
- [ ] `transactions_history_categorized.csv` created
- [ ] `initial_training_data.csv` has ~10,000 rows
- [ ] `streaming_customers_initial_state.csv` has ~2,500 rows
- [ ] `streaming_transactions.csv` created for streaming customers
- [ ] `MASTERFILE.csv` created with 12,500 rows
- [ ] All target columns are 0 for streaming data
- [ ] `streaming_transactions.csv` is sorted by `txn_datetime`

### Phase 2 Verification
- [ ] All 4 simulation scripts start without errors
- [ ] Training progress logs appear
- [ ] GIF files created: `home_loan_simulation.gif`, etc.
- [ ] All scripts complete successfully

### Phase 3 Verification
- [ ] NATS server is running
- [ ] Publisher outputs "Streaming X rows at 20 TPS"
- [ ] Enrichment node shows "✓ Initialized state with 12500 customers"
- [ ] Dispatcher node shows "✓ Home Loan lead rule configured"
- [ ] No errors in any terminal

### Streaming Functionality Test
```bash
# In a 4th terminal, while streaming is active:

# Subscribe to leads
nats-sub "leads.>" --server=nats://localhost:4222

# In another terminal, check what's being published
# Should see JSON messages for qualified leads within 30-90 seconds

# Check MASTERFILE updates
tail -f ./MASTERFILENode/temp_MASTERFILE_stream.csv | head -5
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'pathway'"
**Solution:**
```bash
pip install pathway
```

### Issue: "NATS connection refused"
**Solution:**
```bash
# Check if NATS is running
ps aux | grep nats-server

# If not, install and start
# Ubuntu/Debian:
sudo apt-get install nats-server
nats-server &

# macOS:
brew install nats-server
nats-server &
```

### Issue: "File not found: streaming_transactions.csv"
**Solution:** Make sure you've run `split_data.py` before this step

### Issue: "No leads being published"
**Possible Causes:**
- Customers haven't accumulated enough volume yet
- Cooldown periods not elapsed
- Volume thresholds too high for current transaction stream

**Debug:**
```bash
# Check updated customer profiles
tail -10 ./MASTERFILENode/temp_MASTERFILE_stream.csv | python -c "
import sys, pandas as pd
data = sys.stdin.read()
# Check volTransLastStreamed_home values
"

# Lower thresholds temporarily for testing
# In run_dispatcher_node.py, change:
# HOME_LOAN_VOLUME_THRESHOLD = 10_000  # instead of 100_000
```

---

## Performance Notes

- **Data Generation:** ~30-60 seconds for 12,500 customers with 4 months of transactions
- **Data Splitting:** ~10-20 seconds
- **ML Training:** ~2-5 minutes per model (parallel)
- **Streaming Pipeline:** Runs indefinitely, processes 20 TPS by default

---

## Output Files Summary

After complete execution, expect:

```
/home/shinchan/Projects/TargettedCalling/
├── customers_master_multi_product.csv           # 12,500 customers
├── transactions_history_categorized.csv         # All transactions
├── initial_training_data.csv                    # 10,000 training customers
├── streaming_customers_initial_state.csv        # 2,500 streaming customers
├── streaming_transactions.csv                   # Sorted streaming transactions
├── MASTERFILE.csv                               # Master customer file
├── home_loan_simulation.gif                     # Model visualization
├── car_loan_simulation.gif
├── nifty50_simulation.gif
├── elss_simulation.gif
└── MASTERFILENode/
    ├── temp_MASTERFILE_stream.csv               # Updated customer profiles
    └── temp_MASTERFILE_stream.csv.pathwaymarks  # Pathway metadata
```

---

## Next Steps After Successful Pipeline Run

1. **Analyze Lead Quality:** Check NATS topics for qualified leads
2. **Model Performance:** Review GIF visualizations for model accuracy
3. **Customer Profiles:** Examine `temp_MASTERFILE_stream.csv` for profile updates
4. **Tune Parameters:** Adjust volume thresholds and cooldown periods in `run_dispatcher_node.py`
5. **Scale Testing:** Increase TPS or number of customers for load testing

---

**Total Execution Time:** 
- Phase 1 (Data): ~5-10 minutes
- Phase 2 (ML): ~10-20 minutes (parallel)
- Phase 3 (Streaming): Indefinite (until you stop)
