#!/bin/bash

# Auto detect project directory
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Path to your venv
VENV_PATH="$BASE_DIR/venv/bin/activate"

echo "Starting Pipeline Nodes..."

run_in_terminal() {
    gnome-terminal -- bash -c "
        source $VENV_PATH;
        echo 'Running: $1';
        cd \"$BASE_DIR/$(dirname "$1")\";
        python3 \"$(basename "$1")\";
        exec bash
    "
}

# RUN THESE FILES
#GMM Model
run_in_terminal "carLoanPredictor/run_predictor.py"
run_in_terminal "carLoanFeedback/run_feedback.py"
run_in_terminal "dataUpdater/run_detector_publisher.py"

#report generation nodes
run_in_terminal "report_gen/llm_gen.py"
run_in_terminal "report_gen/read_pred.py"

#Agent caller node
run_in_terminal "carLoanPredictor/caller_node.py"

run_in_terminal "leadPublisher/run_publisher.py"
run_in_terminal "transactionPublisher/run_publisher.py"
run_in_terminal "carLoanPredictor/tester.py"
