#!/bin/bash
###############################################################################
# Complete Pipeline Test Script
###############################################################################

set -e

echo "================================================================================"
echo "COMPLETE NATS PIPELINE TEST"
echo "================================================================================"
echo ""

# Check NATS server
echo "1. Checking NATS server..."
if docker ps | grep -q nats-server; then
    echo "   ✓ NATS server is running"
else
    echo "   ✗ NATS server not running - starting..."
    docker start nats-server 2>/dev/null || docker run -d --name nats-server -p 4222:4222 -p 8222:8222 nats:latest
    sleep 2
    echo "   ✓ NATS server started"
fi
echo ""

# Test data_fetch.py
echo "2. Testing data_fetch.py..."
timeout 5 python data_fetch.py 2>&1 | grep -q "Loading initial data" && echo "   ✓ data_fetch.py works" || echo "   ✗ data_fetch.py failed"
pkill -f data_fetch.py 2>/dev/null || true
echo ""

echo "================================================================================"
echo "READY TO RUN PIPELINE"
echo "================================================================================"
echo ""
echo "Run in 3 separate terminals:"
echo "  Terminal 1: python publishers/stream_all.py"
echo "  Terminal 2: python data_fetch.py"
echo "  Terminal 3: python print_features.py"
echo ""

