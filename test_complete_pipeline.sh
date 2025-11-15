#!/bin/bash

echo "================================"
echo "TESTING COMPLETE NATS PIPELINE"
echo "================================"
echo ""

# Check NATS
echo "1. Checking NATS server..."
if nc -z localhost 4222 2>/dev/null; then
    echo "   ✓ NATS is running"
else
    echo "   ✗ NATS not running. Starting..."
    docker start nats-server 2>/dev/null || docker run -d --name nats-server -p 4222:4222 -p 8222:8222 nats:latest
    sleep 3
fi

# Clean old output
rm -f data/client_features.csv
echo "   Cleaned old output"

echo ""
echo "2. Starting data_fetch.py (Terminal 1 simulation)..."
python data_fetch.py > logs/data_fetch.log 2>&1 &
DATA_PID=$!
echo "   PID: $DATA_PID"
sleep 2

echo ""
echo "3. Starting print_features.py (Terminal 2 simulation)..."
python print_features.py > logs/print_features.log 2>&1 &
PRINT_PID=$!
echo "   PID: $PRINT_PID"
sleep 2

echo ""
echo "4. Starting publishers (Terminal 3 simulation)..."
echo "   Publishing for 15 seconds..."
timeout 15 python publishers/stream_all.py > logs/publishers.log 2>&1

echo ""
echo "5. Waiting for processing..."
sleep 5

echo ""
echo "6. Checking results..."
if [ -f "data/client_features.csv" ]; then
    echo "   ✓ client_features.csv created!"
    echo ""
    echo "   File info:"
    wc -l data/client_features.csv
    ls -lh data/client_features.csv
    echo ""
    echo "   Column count:"
    head -1 data/client_features.csv | tr ',' '\n' | wc -l
    echo ""
    echo "   First few columns:"
    head -1 data/client_features.csv | cut -d',' -f1-10
    echo ""
    echo "   Sample row:"
    head -2 data/client_features.csv | tail -1 | cut -d',' -f1-10
else
    echo "   ✗ client_features.csv NOT found!"
    echo "   Checking logs..."
    echo ""
    echo "   === data_fetch.log ===="
    tail -20 logs/data_fetch.log
    echo ""
    echo "   === print_features.log ==="
    tail -20 logs/print_features.log
fi

echo ""
echo "7. Cleaning up..."
kill $DATA_PID 2>/dev/null
kill $PRINT_PID 2>/dev/null
echo "   Stopped background processes"

echo ""
echo "================================"
echo "TEST COMPLETE"
echo "================================"
