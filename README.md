# TargettedCalling - Stream Processing Platform for Financial Product Recommendations

## 📋 Project Overview

TargettedCalling is a real-time streaming data pipeline system designed to process customer financial transactions and make targeted product recommendations for financial institutions. The platform uses a **hybrid architecture** combining machine learning models (GMM and Neural Networks), streaming data processing, and business rule engines to identify and qualify customers for various financial products.

### Key Products Targeted
- **Home Loan** - Mortgage products
- **Car Loan** - Auto financing products
- **Nifty50 SIP** - Stock market investment recommendations
- **ELSS** - Equity Linked Savings Scheme (tax-saving investment products)

---

## 🏗️ Architecture

The system follows a **distributed streaming architecture** with three main nodes:

```
Data Generation → Data Enrichment → Lead Dispatcher → NATS Topics
     [Source]      [Stateful Node]    [Business Rules]  [Output]
```

### Core Components:

1. **Data Generation Layer** - Generates synthetic customer & transaction data
2. **Enrichment Node** - Real-time customer profile updates using Pathway
3. **Dispatcher Node** - Applies business rules and publishes qualified leads
4. **Transaction Publisher** - Streams transactions via NATS messaging

---

## 📁 Directory Structure

```
TargettedCalling/
├── experiment7/                    # Main experiment folder (ML & simulation logic)
│   ├── create_masterfile.py       # Combines training & streaming data
│   ├── dfcheck.py                 # Data validation utility
│   ├── generate_dataset.py        # Synthetic customer & transaction generation
│   ├── pipeline_config.py         # ML model configurations for each product
│   ├── run_simulation_*.py        # Simulation runners for each product
│   └── split_data.py              # Stratified data split
│
├── MASTERFILENode/                 # Stateful enrichment & dispatch nodes
│   ├── logic.py                   # Customer profile update logic
│   ├── run_dispatcher_node.py     # Lead dispatcher with business rules
│   ├── run_enrichment_node.py     # Real-time customer enrichment
│   └── schema.py                  # Pathway schema for customer data
│
├── transactionPublisher/           # Transaction streaming module
│   ├── run_publisher.py           # Publisher node (NATS)
│   ├── schema.py                  # Transaction data schema
│   └── streamer.py                # CSV-to-stream converter
│
├── add_streaming_columns.py       # Adds streaming-specific columns to masterfile
├── sort_transactions.py           # Chronologically sorts transactions
├── a.py                           # Quick data exploration script
└── README.md                      # This file
```

---

## 🔑 Core Files & Functions

### 1. **experiment7/generate_dataset.py**
**Purpose:** Generates synthetic customer and transaction datasets based on realistic archetypes.

**Key Functions:**
- `define_archetypes_as_recipes()` - Defines 8 customer archetypes with behavioral patterns:
  - Urban Tech Couples (high earners, investment-focused)
  - Tier2 Business Owners (moderate-to-high income, variable transactions)
  - Independent Women Earners (stable salaried professionals)
  - Government Employees (stable, conservative)
  - Financially Stressed (low-income, high transaction volume)
  - High Net Worth (ultra-high earners)
  - Stable Renters (moderate income, stable patterns)
  - First Time Professionals (young professionals, emerging investors)

- `generate_customers(num_customers)` - Creates customer profiles with demographics and financial attributes
- `generate_transactions()` - Creates transaction history for each customer with realistic patterns

**Configuration:**
```python
NUM_CUSTOMERS = 12500
MONTHS_OF_DATA = 4
HIGH_VALUE_TXN_THRESHOLD = 75000
```

---

### 2. **experiment7/split_data.py**
**Purpose:** Performs multi-label stratified split to ensure balanced train/test sets across all target variables.

**Key Functions:**
- `perform_iterative_stratified_split()` - Main function that:
  - Loads master customer and transaction files
  - Uses `MultilabelStratifiedShuffleSplit` to ensure balanced splits
  - Filters transactions for streaming customers only
  - Outputs three CSV files

**Outputs:**
- `initial_training_data.csv` (10,000 customers) - For model training
- `streaming_customers_initial_state.csv` (2,500 customers) - For streaming pipeline
- `streaming_transactions.csv` - Transactions for streaming customers

**Configuration:**
```python
TRAIN_SIZE = 10000
STREAM_SIZE = 2500
TARGET_COLUMNS = ['opted_home_loan', 'opted_car_loan', 'recommend_nifty50', 'recommend_elss']
```

---

### 3. **experiment7/create_masterfile.py**
**Purpose:** Combines training and streaming data into a single master file for the enrichment pipeline.

**Key Functions:**
- `create_combined_masterfile()` - Merges training and streaming datasets:
  - Loads both training and streaming customer files
  - Resets target columns to 0 for streaming data (simulates pre-recommendation state)
  - Combines into single MASTERFILE.csv
  - Outputs combined dataset with initialization columns

**Output:** `MASTERFILE.csv` - Complete customer master data

---

### 4. **add_streaming_columns.py**
**Purpose:** Adds streaming-specific tracking columns to the master file.

**Key Functions:**
- `add_columns_to_masterfile()` - Safely adds new columns:
  - `last_update_timestamp` - Tracks when customer profile was last updated

**Safety Features:**
- Checks if columns already exist (idempotent)
- Safe to run multiple times

---

### 5. **sort_transactions.py**
**Purpose:** Chronologically sorts transactions for proper event-driven simulation.

**Key Functions:**
- `sort_transaction_file_by_datetime()` - Loads, sorts, and saves transactions:
  - Parses `txn_datetime` column as datetime
  - Sorts by timestamp
  - Maintains CSV format

**Critical For:** Event-driven simulations requiring temporal ordering

---

### 6. **experiment7/pipeline_config.py**
**Purpose:** Configuration file defining ML model features for each financial product.

**Key Configurations:**

#### Home Loan Config
```python
HOME_LOAN_CONFIG = {
    "target": "opted_home_loan",
    "gmm_num_features": ['dti_ratio', 'savings_rate', 'income_to_limit', ...],
    "gmm_cat_features": ['city_tier', 'education_level', ...],
    "nn_numerical_features": [...],
    "nn_categorical_features": [...]
}
```

#### Car Loan Config
- Includes transportation spend metrics
- Focus on existing auto loan status

#### Nifty50 Config
- Emphasis on savings behavior and investment patterns
- Targets growth-oriented customers

#### ELSS Config
- Tax-saving focus
- Higher income requirements

**Features Used:**
- **Numerical:** age, income, credit score, spending patterns, ratios
- **Categorical:** gender, marital status, employment, education, city tier

---

### 7. **MASTERFILENode/logic.py**
**Purpose:** Defines real-time customer profile update logic for the streaming pipeline.

**Key Functions:**
- `update_customer_profile(customer_state, transactions)` - Updates customer data based on new transactions:
  
  **Updates Applied:**
  - **Balance Tracking:** Updates `final_avg_monthly_balance` with transaction amounts
  - **Volume Tracking:** Updates `volTransLastStreamed_*` for each product
  - **Credit Score:** Applies penalties for bounced transactions, rewards for successful debits
  - **Transaction Counts:** Updates `txn_count_last_30d` with decay factor (0.98)
  - **Category-Specific Spending:**
    - `monthly_fuel_spend` - Fuel category spend
    - `monthly_transport_service_spend` - Transport category spend
    - `avg_monthly_investment_debit` - Investment category spend
  
  **Derived Features Recalculated:**
  - `savings_rate` - Balance / Monthly Income
  - `txn_intensity` - Transaction count / Income proxy
  - `score_x_log_income` - Credit score × Log(Income)

**Decay Mechanism:** Uses exponential decay (0.98^num_new_txns) for rolling metrics to gradually fade historical data.

---

### 8. **MASTERFILENode/schema.py**
**Purpose:** Defines the Pathway schema for customer master data.

**Schema Categories:**

**Static/Semi-Static Features:**
- Demographics: age, gender, marital status, dependents, occupation, education, city
- Financial: income, account age, initial credit score, existing loans, credit limit

**Dynamic Features (Updated in Real-Time):**
- Aggregations: transaction counts, bounced transactions, spending by category
- Ratios: DTI ratio, savings rate, income-to-limit ratio, transaction intensity
- Interactions: age × dependents, score × log(income)

**Streaming Architecture:**
- `volTransLastStreamed_*` - Volume thresholds for each product (Home, Car, Elss, Nifty50)
- `last_reach_out_*` - Timestamp of last outreach per product (prevents spam)
- `last_update_timestamp` - Latest profile update time

**Target Variables:**
- `opted_home_loan`, `opted_car_loan`, `recommend_nifty50`, `recommend_elss` (0/1 binary)

---

### 9. **MASTERFILENode/run_enrichment_node.py**
**Purpose:** Real-time streaming enrichment node using Pathway.

**Key Functions:**
- `run_enrichment_node()` - Main pipeline orchestrator:

**Pipeline Steps:**
1. Loads initial customer state from `MASTERFILE.csv`
2. Subscribes to transaction stream from NATS topic `transactions.stream`
3. Joins transactions with customer profiles
4. Applies update logic via `update_customer_profile()`
5. Writes updated profiles to `temp_MASTERFILE_stream.csv` in streaming mode

**Key Configuration:**
```python
MASTERFILE_PATH = "./MASTERFILE.csv"
TEMP_OUTPUT_STREAM_FILE = "./MASTERFILENode/temp_MASTERFILE_stream.csv"
NATS_URI = "nats://localhost:4222"
NATS_TOPIC = "transactions.stream"
```

---

### 10. **MASTERFILENode/run_dispatcher_node.py**
**Purpose:** Applies business rules and publishes qualified leads to NATS topics.

**Key Functions:**
- `run_dispatcher_node()` - Dispatcher orchestrator with business rule engine:

**Business Rules (Per Product):**

**Home Loan Leads:**
```python
Volume > 100,000 AND
Not opted yet (opted_home_loan == 0) AND
(Never reached out OR cooldown (90 days) elapsed)
```

**Car Loan Leads:**
```python
Volume > 50,000 AND
Not opted yet (opted_car_loan == 0) AND
(Never reached out OR cooldown (45 days) elapsed)
```

**Nifty50 Leads:**
```python
Volume > 25,000 AND
Not recommended yet (recommend_nifty50 == 0) AND
(Never reached out OR cooldown (30 days) elapsed)
```

**ELSS Leads:**
```python
Volume > 40,000 AND
Not recommended yet (recommend_elss == 0) AND
(Never reached out OR cooldown (60 days) elapsed)
```

**Cooldown System:**
- Prevents customer fatigue through dynamic filtering
- Tracks `last_reach_out_*` timestamps
- Uses "never" string for new leads
- Calculates time difference in seconds for retry eligibility

**Output Streams (NATS Topics):**
- `leads.checkHomeLoan` - Home loan qualified leads
- `leads.checkCarLoan` - Car loan qualified leads
- `leads.checkNifty50` - Nifty50 qualified leads
- `leads.checkElss` - ELSS qualified leads

---

### 11. **transactionPublisher/schema.py**
**Purpose:** Pathway schema for transaction data.

**Schema:**
```python
class TxnSchema(pw.Schema):
    customer_id: str              # Customer identifier
    txn_datetime: datetime        # Transaction timestamp
    txn_amount: float             # Transaction amount (positive: credit, negative: debit)
    txn_type: str                 # Type of transaction
    balance_after_txn: float      # Account balance post-transaction
    bounced_flag: bool            # Whether transaction failed/bounced
    txn_category: str             # Category: Fuel, Transport, Investment, Shopping, Utilities, Misc
```

---

### 12. **transactionPublisher/streamer.py**
**Purpose:** Streams CSV transactions at controlled rate to Pathway.

**Key Functions:**
- `stream_csv_as_file(source_csv, temp_stream_file, tps=20)` - Streams CSV rows to file:
  - Reads entire CSV into memory
  - Creates output file with header
  - Appends rows at controlled rate (TPS = Transactions Per Second)
  - Cycles through rows infinitely for continuous streaming
  - Lightweight logging at 100-row intervals

**Parameters:**
- `source_csv` - Input CSV file path
- `temp_stream_file` - Output file for Pathway to read
- `tps=20` - Transactions per second (default 20)

---

### 13. **experiment7/run_simulation_*.py**
**Purpose:** Machine learning simulations for model training and evaluation.

**Files:**
- `run_simulation_home_loan.py` - Home loan model simulation
- `run_simulation_car_loan.py` - Car loan model simulation
- `run_simulation_nifty50.py` - Nifty50 recommendation simulation
- `run_simulation_elss.py` - ELSS recommendation simulation

**Typical Pipeline:**
1. Load configuration from `pipeline_config.py`
2. Prepare training data with numerical & categorical features
3. Train GMM (Gaussian Mixture Model) and NN (Neural Network) models
4. Generate predictions and visualization (GIF)
5. Evaluate model performance

---

### 14. **experiment7/dfcheck.py**
**Purpose:** Quick data validation utility.

**Function:**
- Loads and displays first few rows of `streaming_transactions.csv`
- Used for quick data verification

---

### 15. **a.py**
**Purpose:** Quick exploration script.

**Function:**
- Loads `MASTERFILE.csv` and prints column names
- Useful for rapid data exploration

---

## 🔄 Processing Pipeline Flow

### Initialization Phase:
```
1. generate_dataset.py
   ↓
   Creates customers_master_multi_product.csv & transactions_history_categorized.csv
   
2. split_data.py
   ↓
   Creates training & streaming datasets with balanced stratification
   
3. create_masterfile.py
   ↓
   Creates MASTERFILE.csv (combined customer data)
   
4. add_streaming_columns.py
   ↓
   Adds streaming tracking columns
   
5. sort_transactions.py
   ↓
   Chronologically sorts streaming_transactions.csv
```

### Streaming Phase:
```
1. run_publisher.py
   └─→ Streams transactions via NATS at configured TPS
   
2. run_enrichment_node.py
   ├─→ Reads initial customer state from MASTERFILE.csv
   ├─→ Joins with transaction stream
   ├─→ Updates profiles via logic.py
   └─→ Outputs updated profiles
   
3. run_dispatcher_node.py
   ├─→ Applies business rules
   ├─→ Enforces cooldown periods
   └─→ Publishes qualified leads to NATS topics
```

### ML Training Phase (Parallel):
```
run_simulation_*.py
├─→ Load trained data
├─→ Train GMM & NN models
├─→ Generate predictions
└─→ Create visualization GIFs
```

---

## 📊 Data Flow Schema

### Master Customer Schema Fields:

**Demographics:**
- customer_id, age, gender, marital_status, dependents_count, occupation, education_level, city_tier

**Financial Profile:**
- yearly_income, account_age_months, initial_credit_score, existing_loans_count, total_credit_limit

**Dynamic Metrics (Updated Streaming):**
- final_avg_monthly_balance, final_credit_score, bounced_txn_count, txn_count_last_30d
- monthly_fuel_spend, monthly_transport_service_spend, avg_monthly_investment_debit

**Derived Ratios:**
- dti_ratio (Debt-To-Income), savings_rate, txn_intensity, income_to_limit ratio

**Interaction Features:**
- age_x_dependents, score_x_log_income

**Streaming Volume Trackers:**
- volTransLastStreamed_home, volTransLastStreamed_car, volTransLastStreamed_elss, volTransLastStreamed_nifty50

**Outreach Tracking:**
- last_reach_out_home_loan, last_reach_out_car_loan, last_reach_out_nifty50, last_reach_out_elss

**Targets:**
- opted_home_loan, opted_car_loan, recommend_nifty50, recommend_elss (binary 0/1)

---

## 🚀 Quick Start

### 1. Generate Dataset
```bash
python experiment7/generate_dataset.py
```

### 2. Split Data
```bash
python experiment7/split_data.py
```

### 3. Create Master File
```bash
python experiment7/create_masterfile.py
```

### 4. Add Streaming Columns
```bash
python add_streaming_columns.py
```

### 5. Sort Transactions
```bash
python sort_transactions.py
```

### 6. Run Streaming Pipeline
```bash
# Terminal 1: Publisher
python transactionPublisher/run_publisher.py

# Terminal 2: Enrichment Node
python MASTERFILENode/run_enrichment_node.py

# Terminal 3: Dispatcher Node
python MASTERFILENode/run_dispatcher_node.py
```

### 7. Run ML Simulations (Parallel)
```bash
python experiment7/run_simulation_home_loan.py
python experiment7/run_simulation_car_loan.py
python experiment7/run_simulation_nifty50.py
python experiment7/run_simulation_elss.py
```

---

## 🛠️ Key Technologies

- **Pathway** - Streaming dataflow framework
- **Pandas** - Data manipulation
- **NumPy** - Numerical computations
- **Faker** - Synthetic data generation
- **scikit-learn** - ML models (GMM, preprocessing)
- **NATS** - Message broker for event streaming
- **Matplotlib/PIL** - Visualization

---

## ⚙️ Configuration Parameters

### Dataset Generation
- NUM_CUSTOMERS: 12,500 (10,000 train + 2,500 stream)
- MONTHS_OF_DATA: 4 months of history
- HIGH_VALUE_TXN_THRESHOLD: 75,000 (INR)

### Streaming Pipeline
- TPS: 20 transactions per second (configurable)
- Autocommit Duration: 100ms

### Business Rules
- Home Loan Volume Threshold: 100,000
- Car Loan Volume Threshold: 50,000
- Nifty50 Volume Threshold: 25,000
- ELSS Volume Threshold: 40,000

### Cooldown Periods
- Home Loan: 90 days
- Car Loan: 45 days
- Nifty50: 30 days
- ELSS: 60 days

---

## 📝 Notes

- **Idempotent Operations:** Scripts like `add_streaming_columns.py` check for existing columns before adding
- **Stratified Splits:** Ensures balanced representation of all target variables in train/test sets
- **Decay Mechanism:** Rolling metrics use exponential decay to fade historical data in streaming context
- **Cooldown System:** Prevents customer fatigue by enforcing time-based wait periods between outreach campaigns
- **Event Ordering:** Transactions must be sorted chronologically for proper simulation

---

## 🔐 Important Notes

1. **Pathway Streaming Mode:** Uses file-based streaming; ensure temp files are writable
2. **NATS Configuration:** Requires running NATS server at localhost:4222
3. **Data Directory:** All scripts assume CSV files in current working directory
4. **Idempotency:** Most scripts are safe to run multiple times (except data generation)

---

## 📧 Contact & Support

For questions regarding the pipeline architecture, model configurations, or data flow, refer to the inline comments in each module.

---

**Last Updated:** November 24, 2025  
**Project Branch:** re-factor
