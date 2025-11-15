# Real-Time Banking Feature Pipeline

## Overview

Real-time banking data pipeline using NATS for streaming and feature calculation.

## Architecture

```
stream_tables/  →  NATS  →  data_fetch.py  →  NATS  →  print_features.py  →  data/client_features.csv
   (CSV)       publishers    (Calculate)      features        (Save)
```

## Quick Start

### 1. Start NATS Server
```bash
docker run -d --name nats-server -p 4222:4222 -p 8222:8222 nats:latest
```

### 2. Start Data Processor (Terminal 1)
```bash
python data_fetch.py
```

### 3. Start Feature Saver (Terminal 2)
```bash
python print_features.py
```

### 4. Start Publishers (Terminal 3)
```bash
python publishers/stream_all.py
```

## Files

### Publishers
- `publishers/stream_all.py` - Master publisher (runs all)
- `publishers/publish_initial.py` - Publishes base data
- `publishers/stream_*.py` - Individual table publishers

### Processing
- `data_fetch.py` - Subscribes to NATS, calculates features, publishes to features topic
- `print_features.py` - Subscribes to features topic, saves to CSV
- `nats_config.py` - Configuration (topics, paths, rates)

### Data
- `data/present_tables/` - Base data for initialization
- `data/stream_tables/` - Streaming data
- `data/client_features.csv` - Output (calculated features)

## Workflow

1. **publishers/stream_all.py**:
   - Publishes initial data from present_tables to NATS
   - Streams data from stream_tables to NATS topics

2. **data_fetch.py**:
   - Subscribes to banking.tables.* topics
   - Maintains in-memory data store
   - Calculates client features every 50 messages
   - Publishes to banking.features.client topic

3. **print_features.py**:
   - Subscribes to banking.features.client topic
   - Buffers features
   - Saves to data/client_features.csv every 100 messages

## Monitoring

- NATS Dashboard: http://localhost:8222
- Watch output: `tail -f data/client_features.csv`

## Features Calculated

- **Transaction**: 22 features (amounts, counts, ratios, etc.)
- **Loan**: 13 features (amounts, duration, payments)
- **Order**: 7 features (amounts, counts, banks)
- **Card**: 9 features (counts by type, dates)
- **District**: 16 features (demographics A1-A16)
- **Client**: Basic info (birth_number, district_id)

**Total**: 67+ features per client
