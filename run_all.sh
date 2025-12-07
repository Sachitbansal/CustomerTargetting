#!/bin/bash

echo "Starting Full Targeted Calling Pipeline..."

# Auto-detect project directory
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Path to venv
VENV_PATH="$BASE_DIR/venv/bin/activate"

###############################################
# ACTIVATE VENV
###############################################
source "$VENV_PATH"
echo "Python env activated."

###############################################
#   PREPROCESSING STEPS (sequential)
###############################################
echo ""
echo "🧹 Cleaning old CSV files..."
rm -f "$BASE_DIR/MASTERFILE.csv"
rm -f "$BASE_DIR/streaming_transactions.csv"
rm -f "$BASE_DIR/datasetGeneration/streaming_transactions.csv"

echo ""
echo "⚙️  Running dataset preprocessing pipeline..."

echo "1️⃣ generate_dataset.py"
python3 "$BASE_DIR/datasetGeneration/generate_dataset.py"

echo "2️⃣ split_data.py"
python3 "$BASE_DIR/datasetGeneration/split_data.py"

echo "3️⃣ create_masterfile.py"
python3 "$BASE_DIR/datasetGeneration/create_masterfile.py"

echo "4️⃣ add_streaming_columns.py"
python3 "$BASE_DIR/datasetGeneration/add_streaming_columns.py"

echo ""
echo "📂 Moving CSV files if they exist..."

# MASTERFILE usually saved in BASE_DIR already
if [ -f "$BASE_DIR/datasetGeneration/MASTERFILE.csv" ]; then
    mv "$BASE_DIR/datasetGeneration/MASTERFILE.csv" "$BASE_DIR/"
fi

# streaming_transactions saved inside datasetGeneration
if [ -f "$BASE_DIR/datasetGeneration/streaming_transactions.csv" ]; then
    mv "$BASE_DIR/datasetGeneration/streaming_transactions.csv" "$BASE_DIR/"
fi

echo ""
echo "🚀 Running Initial Car Loan Trainer..."
python3 "$BASE_DIR/carLoanPredictor/init_car_trainer.py"


##################################################
#          NODE DEFINITIONS (your format)
##################################################

declare -a NODES=(

    # MASTERFILE + Detector pipeline
    "carLoanPredictor:run_predictor.py"
    "carLoanFeedback:run_feedback.py"
    "dataUpdater:run_detector_publisher.py"
    "oracle:run_feedback.py"

    # Publishers
    "leadPublisher:run_publisher.py"
    "transactionPublisher:run_publisher.py"

    # Misc
    "carLoanPredictor:tester.py"
)

echo ""
echo "============================================"
echo "🚀 Starting all pipeline nodes..."
echo "============================================"

##################################################
#          NODE LAUNCH LOOP
##################################################
for node in "${NODES[@]}"; do
    IFS=':' read -r folder script <<< "$node"
    echo "▶️  Starting $script in $folder ..."
    
    (
        cd "$BASE_DIR/$folder" || exit
        source "$VENV_PATH"
        python3 "$script"
    ) &
    
    sleep 1
done

echo ""
echo "✓ All nodes launched in background!"
echo "Press Ctrl+C to stop everything."
echo ""

wait
