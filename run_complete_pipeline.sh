#!/bin/bash
###############################################################################
# Complete NATS-Based Streaming Pipeline
#
# This script demonstrates the proper workflow for the NATS-based architecture:
# 1. Start NATS server (if not running)
# 2. Publish initial data from present_tables to NATS
# 3. Run data_fetch.py to process data and calculate features
# 4. Run NATS publishers to stream updates from stream_tables
# 5. Run print_features.py to save features to CSV
#
# Usage:
#   ./run_complete_pipeline.sh
###############################################################################

set -e  # Exit on error

echo "================================================================================"
echo "COMPLETE NATS-BASED STREAMING PIPELINE"
echo "================================================================================"
echo ""

# Step 1: Check/Start NATS server
echo "Step 1: Checking NATS server..."
if docker ps | grep -q nats-server; then
    echo "✓ NATS server is running"
else
    echo "Starting NATS server..."
    if docker ps -a | grep -q nats-server; then
        docker start nats-server
    else
        docker run -d --name nats-server -p 4222:4222 -p 8222:8222 nats:latest
    fi
    echo "✓ NATS server started"
    sleep 2
fi
echo ""

# Step 2: Publish initial data to NATS
echo "Step 2: Publishing initial data from present_tables to NATS..."
echo "This will send all present_tables data to NATS topics"
python publishers/publish_initial.py
echo ""

# Step 3: Start data_fetch.py (processes data and calculates features)
echo "Step 3: Starting data_fetch.py to process data..."
echo "This will:"
echo "  - Load data from present_tables (static)"
echo "  - Calculate client features"
echo "  - Output to data/client_features.csv"
echo ""
echo "Press Ctrl+C when done processing to continue..."
python data_fetch.py
echo ""

# Step 4: Start NATS publishers (optional - for streaming updates)
echo "Step 4: Starting NATS publishers for streaming updates..."
echo "This will stream data from stream_tables/ to NATS"
echo ""
echo "To run publishers, execute in a separate terminal:"
echo "  python publishers/stream_all_nats.py"
echo ""

echo "================================================================================"
echo "PIPELINE SETUP COMPLETE"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Check output: cat data/client_features.csv | head -20"
echo "  2. Monitor NATS: http://localhost:8222"
echo "  3. For streaming updates, run: python publishers/stream_all_nats.py"
echo ""
