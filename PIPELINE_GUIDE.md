# Complete NATS-Based Streaming Pipeline Guide

## Overview

The pipeline now consists of **3 main components** that communicate via NATS:

1. **stream_all.py** - Publishes data from `stream_tables/` to NATS
2. **data_fetch.py** - Subscribes to NATS, calculates features, publishes to NATS
3. **print_features.py** - Subscribes to features from NATS, saves to CSV

## Architecture

```
stream_tables/*.csv
        ↓
  stream_all.py (Publishers)
        ↓
   NATS Topics (banking.tables.*)
        ↓
  data_fetch.py (Feature Calculator)
        ├── Loads present_tables/ initially (CSV)
        ├── Subscribes to NATS for updates
        ├── Calculates features
        └── Publishes to banking.features.client
        ↓
   NATS Topic (banking.features.client)
        ↓
  print_features.py (Feature Saver)
        └── Saves to data/client_features.csv
```

## Quick Start

### Prerequisites
```bash
# Start NATS server
docker start nats-server

# Or create new container
docker run -d --name nats-server -p 4222:4222 -p 8222:8222 nats:latest
```

### Running the Complete Pipeline

**Terminal 1 - Data Processor** (Start this first):
```bash
python data_fetch.py
```
This will:
- Load initial data from `present_tables/`
- Connect to NATS
- Subscribe to all table topics
- Calculate and publish initial features
- Wait for streaming updates

**Terminal 2 - Feature Saver**:
```bash
python print_features.py
```
This will:
- Connect to NATS
- Subscribe to `banking.features.client`
- Save features to `data/client_features.csv` every 100 messages

**Terminal 3 - Data Publishers**:
```bash
python publishers/stream_all.py
```
This will:
- Connect to NATS
- Publish data from `stream_tables/` to NATS topics
- Remove rows from stream_tables as they're published

## Component Details

### 1. stream_all.py

**Location**: `publishers/stream_all.py`

**What it does**:
- Reads data from `stream_tables/*.csv`
- Publishes to NATS topics (e.g., `banking.tables.trans`)
- Removes rows from CSV files as they're published
- Runs async publishers concurrently

**Usage**:
```bash
# Default configuration
python publishers/stream_all.py

# Override delay for all publishers
python publishers/stream_all.py --delay 2.0
```

**Configuration** (in `stream_all_async.py`):
```python
PUBLISHER_CONFIG = {
    'trans': {'batch_size': 20, 'delay': 12.0},
    'account': {'batch_size': 10, 'delay': 4.0},
    # ... etc
}
```

### 2. data_fetch.py

**Location**: `data_fetch.py`

**What it does**:
- **Initial Load**: Reads all data from `present_tables/` into memory
- **NATS Subscription**: Subscribes to all banking.tables.* topics
- **Feature Calculation**: Calculates client features every N messages
- **NATS Publishing**: Publishes features to `banking.features.client`

**Key Features**:
- In-memory data stores (clients, accounts, transactions, etc.)
- Real-time feature calculation
- Automatic feature updates on new data
- Publishes features to NATS (not CSV)

**Configuration**:
```python
self.calc_every_n_messages = 50  # Calculate features every 50 messages
```

**Usage**:
```bash
python data_fetch.py
```

### 3. print_features.py

**Location**: `print_features.py`

**What it does**:
- Subscribes to `banking.features.client` on NATS
- Buffers incoming feature messages
- Saves to `data/client_features.csv` every 100 messages or 30 seconds
- Removes duplicates (keeps latest per client)

**Usage**:
```bash
python print_features.py
```

**Output**:
- File: `data/client_features.csv`
- Format: CSV with all client features
- Updates: Every 100 messages or 30 seconds

## Data Flow

1. **Initial State**:
   - `present_tables/` contains base data
   - `stream_tables/` contains data to be streamed

2. **Startup Sequence**:
   - Start NATS server
   - Start `data_fetch.py` (loads present_tables)
   - Start `print_features.py` (waits for features)
   - Start `stream_all.py` (begins publishing)

3. **Streaming**:
   - `stream_all.py` publishes rows to NATS
   - `data_fetch.py` receives updates, calculates features
   - Features published to NATS
   - `print_features.py` saves features to CSV

## NATS Topics

Defined in `nats_config.py`:

```python
SUBJECTS = {
    # Table topics (published by stream_all.py)
    'client': 'banking.tables.client',
    'account': 'banking.tables.account',
    'trans': 'banking.tables.trans',
    'loan': 'banking.tables.loan',
    'order': 'banking.tables.order',
    'card': 'banking.tables.card',
    'disp': 'banking.tables.disp',
    'district': 'banking.tables.district',
    'loan_labels': 'banking.tables.loan_labels',
    'card_labels': 'banking.tables.card_labels',

    # Feature topic (published by data_fetch.py)
    'client_features': 'banking.features.client'
}
```

## Features Calculated

For each client:
- **Transaction Features**:
  - num_transactions, total_incoming, total_outgoing
  - avg_incoming, avg_outgoing, net_cashflow
- **Loan Features**:
  - num_loans, total_loan_amount, avg_loan_amount, avg_loan_duration
- **Order Features**:
  - num_orders, total_order_amount, avg_order_amount
- **Card Features**:
  - num_cards
- **District Features**:
  - A1-A16 (demographic data)
- **Client Info**:
  - client_id, birth_number, district_id

## Monitoring

### NATS Dashboard
- URL: http://localhost:8222
- Shows active connections, subscriptions, message counts

### Console Output
- **stream_all.py**: Shows publishing progress per table
- **data_fetch.py**: Shows message count, feature calculation progress
- **print_features.py**: Shows features received, save operations

### Output File
```bash
# Watch the output file grow
tail -f data/client_features.csv

# Count features
wc -l data/client_features.csv
```

## Troubleshooting

### Issue: ConnectionRefusedError
**Solution**: Start NATS server
```bash
docker start nats-server
```

### Issue: No features appearing
**Checklist**:
1. ✓ NATS server running
2. ✓ data_fetch.py started and loaded present_tables
3. ✓ print_features.py started and subscribed
4. ✓ stream_all.py publishing data

### Issue: stream_tables files empty
**Solution**: Restore from backup or regenerate
```bash
# Your data split script should regenerate stream_tables
python data_fetch.py  # Or your data preparation script
```

## File Structure

```
TargettedCalling/
├── data/
│   ├── present_tables/      # Initial static data (CSV)
│   ├── stream_tables/        # Streaming data (CSV, modified by publishers)
│   └── client_features.csv   # Output features
├── publishers/
│   ├── stream_all.py         # Main entry point (wrapper)
│   ├── stream_all_async.py   # Actual async implementation
│   ├── stream_account.py     # Individual publishers
│   ├── stream_trans.py       # (each has async continuous function)
│   └── ...
├── data_fetch.py             # NATS-based feature calculator
├── print_features.py         # NATS-based feature saver
├── nats_config.py            # NATS configuration
└── test_pipeline.sh          # Test script
```

## Summary

The pipeline is now **fully NATS-based**:
- ✅ No CSV streaming mode conflicts
- ✅ Clean separation of concerns
- ✅ Real-time feature calculation
- ✅ Scalable architecture
- ✅ Easy to monitor and debug

All communication between components happens via NATS, making the system modular and extensible.
