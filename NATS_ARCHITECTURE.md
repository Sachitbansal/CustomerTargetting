# NATS-Based Streaming Architecture

## Overview

This project now uses a proper NATS-based architecture where:
- **present_tables/** contains static initial data
- **stream_tables/** contains data to be streamed via NATS
- **NATS** handles all real-time data streaming
- **Pathway** processes static data and calculates features

## Architecture Changes

### Previous (Broken) Architecture
- ❌ data_fetch.py tried to read stream_tables in CSV streaming mode
- ❌ Publishers modified stream_tables while Pathway was reading them
- ❌ Caused `TryFromIntError` due to file conflicts

### New (Fixed) Architecture
- ✅ data_fetch.py reads only present_tables (static mode)
- ✅ Publishers stream from stream_tables to NATS
- ✅ No file conflicts - clean separation of concerns

## Components

### 1. NATS Server
```bash
# Start NATS server
docker start nats-server

# Or create new container
docker run -d --name nats-server -p 4222:4222 -p 8222:8222 nats:latest

# Monitor at http://localhost:8222
```

### 2. Data Processing (data_fetch.py)
- Reads static data from `present_tables/`
- Calculates client features using Pathway
- Outputs to `data/client_features.csv`
- **No longer uses CSV streaming mode**

```bash
python data_fetch.py
```

### 3. NATS Publishers

#### Option A: Async Continuous Publishers (Recommended)
Streams data from stream_tables to NATS, modifying files as rows are published:

```bash
python publishers/stream_all_nats.py
```

Individual publishers:
```bash
python publishers/stream_account.py
python publishers/stream_trans.py
# ... etc
```

#### Option B: Sync Wrapper Publishers (For stream_all.py compatibility)
The sync wrappers created earlier work but don't actually publish to NATS:

```bash
python publishers/stream_all.py --mode single
python publishers/stream_all.py --mode continuous
```

### 4. Initial Data Publisher
Publishes all present_tables data to NATS as initial state:

```bash
python publishers/publish_initial.py
```

## Workflow

### Quick Start (Batch Processing)
```bash
# 1. Start NATS
docker start nats-server

# 2. Process data
python data_fetch.py

# 3. Check output
head data/client_features.csv
```

### Full Streaming Pipeline
```bash
# Terminal 1: NATS Server
docker start nats-server

# Terminal 2: Publish initial data
python publishers/publish_initial.py

# Terminal 3: Data processor
python data_fetch.py

# Terminal 4: Stream publishers
python publishers/stream_all_nats.py
```

## Files Modified

### data_fetch.py
- ✅ Removed all CSV streaming reads
- ✅ Uses only present_tables in static mode
- ✅ No more file conflicts with publishers

### Publishers
Each publisher has two functions:
1. **`stream_X_continuous()`** - Async function that publishes to NATS
2. **`stream_X()`** - Sync wrapper for stream_all.py (doesn't use NATS)

### New Scripts
- **`publishers/stream_all_nats.py`** - Runs all async publishers concurrently
- **`run_complete_pipeline.sh`** - Complete workflow script
- **`publishers/stream_state.json`** - State tracking for sync wrappers

## Data Flow

```
present_tables/*.csv (static)
    ↓
data_fetch.py (Pathway processing)
    ↓
data/client_features.csv

stream_tables/*.csv
    ↓
NATS Publishers (async continuous)
    ↓
NATS Topics (banking.tables.*)
    ↓
[Future: Subscribe and process real-time]
```

## Configuration

### NATS Topics (nats_config.py)
```python
SUBJECTS = {
    'client': 'banking.tables.client',
    'account': 'banking.tables.account',
    'trans': 'banking.tables.trans',
    # ... etc
}
```

### Publisher Settings (stream_all_nats.py)
```python
stream_account_continuous(batch_size=10, delay=4.0)
stream_trans_continuous(batch_size=20, delay=12.0)
# ... etc
```

## Troubleshooting

### Issue: ConnectionRefusedError
**Solution**: Start NATS server
```bash
docker start nats-server
```

### Issue: TryFromIntError
**Solution**: This should be fixed now. If it occurs:
- Make sure data_fetch.py doesn't read from stream_tables
- Don't run data_fetch.py while publishers are modifying stream_tables

### Issue: Parse errors in district.csv
**Cause**: Some district data has "?" values that can't be parsed as floats
**Impact**: Minor - a few district records may be skipped
**Solution**: Clean the data or handle nulls in schema

## Next Steps

To fully utilize NATS for streaming:
1. Modify data_fetch.py to subscribe to NATS topics
2. Process incoming NATS messages in real-time
3. Update features incrementally as new data arrives
4. Publish calculated features back to NATS

This would require a custom Pathway connector or Python-based streaming processor.
