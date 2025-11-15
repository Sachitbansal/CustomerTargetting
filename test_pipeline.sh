#!/bin/bash
echo "Testing NATS Real-Time Pipeline"
echo "================================"
echo ""
echo "Starting data_fetch.py in background..."
python data_fetch.py > logs/data_fetch.log 2>&1 &
DATA_FETCH_PID=$!
echo "  PID: $DATA_FETCH_PID"

sleep 2

echo "Starting print_features.py in background..."
python print_features.py > logs/print_features.log 2>&1 &
PRINT_PID=$!
echo "  PID: $PRINT_PID"

sleep 2

echo ""
echo "Publishing 20 transactions..."
timeout 5 python publishers/stream_trans.py 2>&1 | head -20

sleep 3

echo ""
echo "Checking output..."
if [ -f "data/client_features.csv" ]; then
    echo "✓ client_features.csv created"
    wc -l data/client_features.csv
    head -3 data/client_features.csv | cut -d',' -f1-5
else
    echo "✗ client_features.csv not found"
fi

echo ""
echo "Stopping processes..."
kill $DATA_FETCH_PID 2>/dev/null
kill $PRINT_PID 2>/dev/null
echo "Done!"
