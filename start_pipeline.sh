#!/bin/bash

echo "Starting NATS Streaming Pipeline..."

# CHANGE THIS to your actual path
BASE_DIR="/root/interiit/TargettedCalling"

# Array of folders and their corresponding scripts
declare -a NODES=(
    "MASTERFILENode:run_enrichment_node.py"
    "MASTERFILENode:run_dispatcher_node.py"
    "carLoanPredictor:car_loan_prediction_node.py"
    "carLoanPredictor:car_loan_feedback_node.py"
    "report_gen:read_pred.py"
    "report_gen:llm_gen.py"
    "carLoanPredictor:caller_node.py"
    "transactionPublisher:run_publisher.py"
)

# Start each node
for node in "${NODES[@]}"; do
    IFS=':' read -r folder script <<< "$node"
    echo "Starting $script in $folder folder..."
    cd "$BASE_DIR/$folder" && python3 $script &
    sleep 2
done

echo ""
echo "✓ All 8 nodes started successfully!"
echo "Press Ctrl+C to stop all nodes"
echo ""

# Keep script running
wait
