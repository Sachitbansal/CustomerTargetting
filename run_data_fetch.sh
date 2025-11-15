#!/bin/bash

# Run script for data_fetch.py with error handling

echo "=========================================="
echo "Starting Pathway Data Fetch Pipeline"
echo "=========================================="
echo ""

# Check if present_tables exists
if [ ! -d "data/present_tables" ]; then
    echo "❌ Error: data/present_tables directory not found!"
    echo "Please ensure data files are in place."
    exit 1
fi

# Check if CSV files exist
REQUIRED_FILES=("client.csv" "account.csv" "disp.csv" "trans.csv" "loan.csv" "order.csv" "card.csv" "district.csv")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "data/present_tables/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -ne 0 ]; then
    echo "❌ Missing files in data/present_tables/:"
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    exit 1
fi

echo "✓ All required CSV files found"
echo ""

# Create output directory
mkdir -p data/pathway_output
echo "✓ Output directory created/exists"
echo ""

# Run the pipeline
echo "Starting pipeline..."
echo "Press Ctrl+C to stop"
echo ""

python data_fetch.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Pipeline completed successfully"
    echo "=========================================="
elif [ $EXIT_CODE -eq 130 ]; then
    echo ""
    echo "=========================================="
    echo "Pipeline stopped by user (Ctrl+C)"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "Pipeline exited with error code: $EXIT_CODE"
    echo "=========================================="
fi

exit $EXIT_CODE
