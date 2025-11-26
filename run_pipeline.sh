#!/bin/bash

# COMPLETE PIPELINE EXECUTION SCRIPT
# This script automates all steps for running the TargettedCalling pipeline

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/shinchan/Projects/TargettedCalling"
NATS_PORT=4222

# Functions
print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if running from correct directory
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Menu
show_menu() {
    echo ""
    echo -e "${BLUE}Select operation:${NC}"
    echo "1) Run full pipeline (Phase 1 + Phase 2 + setup for Phase 3)"
    echo "2) Run Phase 1 only (Data generation & preparation)"
    echo "3) Run Phase 2 only (ML Model training)"
    echo "4) Setup Phase 3 (Start streaming pipeline in new terminals)"
    echo "5) Test Phase 1 (Verify generated data)"
    echo "6) Clean up (Remove generated files)"
    echo "7) Exit"
    echo ""
    read -p "Enter your choice [1-7]: " choice
}

# Phase 1: Data Generation & Preparation
run_phase_1() {
    print_header "PHASE 1: DATA GENERATION & PREPARATION"
    
    print_info "Step 1/5: Generating synthetic dataset..."
    if python experiment7/generate_dataset.py; then
        print_success "Dataset generated"
    else
        print_error "Dataset generation failed"
        exit 1
    fi
    
    print_info "Step 2/5: Splitting data into train and stream sets..."
    if python experiment7/split_data.py; then
        print_success "Data split complete"
    else
        print_error "Data split failed"
        exit 1
    fi
    
    print_info "Step 3/5: Creating master file..."
    if python experiment7/create_masterfile.py; then
        print_success "Master file created"
    else
        print_error "Master file creation failed"
        exit 1
    fi
    
    print_info "Step 4/5: Adding streaming columns..."
    if python add_streaming_columns.py; then
        print_success "Streaming columns added"
    else
        print_error "Failed to add streaming columns"
        exit 1
    fi
    
    print_info "Step 5/5: Sorting transactions chronologically..."
    if python sort_transactions.py; then
        print_success "Transactions sorted"
    else
        print_error "Transaction sorting failed"
        exit 1
    fi
    
    print_header "PHASE 1 COMPLETE ✓"
}

# Phase 2: ML Model Training
run_phase_2() {
    print_header "PHASE 2: ML MODEL TRAINING"
    
    print_info "Training 4 models in parallel..."
    print_info "  - Home Loan model"
    print_info "  - Car Loan model"
    print_info "  - Nifty50 model"
    print_info "  - ELSS model"
    
    # Start all models in background
    python experiment7/run_simulation_home_loan.py > /tmp/home_loan.log 2>&1 &
    HOME_LOAN_PID=$!
    
    python experiment7/run_simulation_car_loan.py > /tmp/car_loan.log 2>&1 &
    CAR_LOAN_PID=$!
    
    python experiment7/run_simulation_nifty50.py > /tmp/nifty50.log 2>&1 &
    NIFTY50_PID=$!
    
    python experiment7/run_simulation_elss.py > /tmp/elss.log 2>&1 &
    ELSS_PID=$!
    
    print_info "Models training in background..."
    print_info "  Home Loan PID: $HOME_LOAN_PID"
    print_info "  Car Loan PID: $CAR_LOAN_PID"
    print_info "  Nifty50 PID: $NIFTY50_PID"
    print_info "  ELSS PID: $ELSS_PID"
    
    # Wait for all models to complete
    wait $HOME_LOAN_PID $CAR_LOAN_PID $NIFTY50_PID $ELSS_PID
    
    print_success "All models trained successfully"
    print_info "Generated files:"
    ls -lh *.gif 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    
    print_header "PHASE 2 COMPLETE ✓"
}

# Setup Phase 3: Streaming Pipeline
setup_phase_3() {
    print_header "PHASE 3: STREAMING PIPELINE SETUP"
    
    # Check NATS
    print_info "Checking NATS server..."
    if nc -z localhost $NATS_PORT 2>/dev/null; then
        print_success "NATS server is running"
    else
        print_warning "NATS server not detected. Starting it..."
        if command -v nats-server &> /dev/null; then
            nats-server &
            sleep 2
            print_success "NATS server started (PID: $!)"
        else
            print_error "NATS server not installed. Please install it:"
            echo "  Ubuntu: sudo apt-get install nats-server"
            echo "  macOS: brew install nats-server"
            echo "  Then run: nats-server &"
            exit 1
        fi
    fi
    
    print_header "READY FOR PHASE 3"
    echo ""
    echo -e "${YELLOW}Please open 3 new terminal windows and run:${NC}"
    echo ""
    echo -e "${BLUE}Terminal 1 - Transaction Publisher:${NC}"
    echo "  cd $PROJECT_DIR && python transactionPublisher/run_publisher.py"
    echo ""
    echo -e "${BLUE}Terminal 2 - Enrichment Node:${NC}"
    echo "  cd $PROJECT_DIR && python MASTERFILENode/run_enrichment_node.py"
    echo ""
    echo -e "${BLUE}Terminal 3 - Lead Dispatcher:${NC}"
    echo "  cd $PROJECT_DIR && python MASTERFILENode/run_dispatcher_node.py"
    echo ""
    echo -e "${YELLOW}Optional Terminal 4 - Monitor NATS Topics:${NC}"
    echo "  nats-sub \"leads.>\" --server=nats://localhost:$NATS_PORT"
    echo ""
    
    read -p "Press Enter to continue..."
}

# Test Phase 1 Output
test_phase_1() {
    print_header "PHASE 1 VERIFICATION"
    
    echo -e "\n${BLUE}File Sizes:${NC}"
    for file in customers_master_multi_product.csv transactions_history_categorized.csv \
                initial_training_data.csv streaming_customers_initial_state.csv \
                streaming_transactions.csv MASTERFILE.csv; do
        if [ -f "$file" ]; then
            lines=$(wc -l < "$file")
            size=$(du -h "$file" | cut -f1)
            echo "  ✓ $file: $lines lines, $size"
        else
            echo "  ✗ $file: NOT FOUND"
        fi
    done
    
    echo -e "\n${BLUE}Data Quality Checks:${NC}"
    python3 << 'EOF'
import pandas as pd
import sys

try:
    # Check MASTERFILE
    df = pd.read_csv('MASTERFILE.csv')
    print(f"  ✓ MASTERFILE.csv: {len(df)} customers, {df.shape[1]} features")
    
    # Check stratification
    df_train = pd.read_csv('initial_training_data.csv')
    df_stream = pd.read_csv('streaming_customers_initial_state.csv')
    
    targets = ['opted_home_loan', 'opted_car_loan', 'recommend_nifty50', 'recommend_elss']
    print(f"\n  Target Column Distribution:")
    for col in targets:
        if col in df_train.columns and col in df_stream.columns:
            train_mean = df_train[col].mean()
            stream_mean = df_stream[col].mean()
            print(f"    {col}: Train={train_mean:.3f}, Stream={stream_mean:.3f}")
    
    # Check transaction sorting
    df_txn = pd.read_csv('streaming_transactions.csv', parse_dates=['txn_datetime'])
    is_sorted = df_txn['txn_datetime'].is_monotonic_increasing
    print(f"\n  ✓ Transactions sorted: {is_sorted}")
    print(f"  ✓ Transaction date range: {df_txn['txn_datetime'].min()} to {df_txn['txn_datetime'].max()}")
    
except Exception as e:
    print(f"  ✗ Error: {str(e)}")
    sys.exit(1)
EOF
    
    print_header "PHASE 1 VERIFICATION COMPLETE ✓"
}

# Cleanup
cleanup() {
    print_header "CLEANUP"
    
    read -p "Are you sure you want to delete all generated files? (y/n): " confirm
    if [ "$confirm" = "y" ]; then
        print_info "Removing generated files..."
        rm -f *.csv *.gif 2>/dev/null
        rm -f MASTERFILENode/temp_MASTERFILE_stream.csv* 2>/dev/null
        print_success "Cleanup complete"
    else
        print_warning "Cleanup cancelled"
    fi
}

# Main loop
while true; do
    show_menu
    
    case $choice in
        1)
            run_phase_1
            read -p "Do you want to start Phase 2 (ML training) now? (y/n): " ans
            if [ "$ans" = "y" ]; then
                run_phase_2
            fi
            read -p "Do you want to setup Phase 3 (streaming)? (y/n): " ans
            if [ "$ans" = "y" ]; then
                setup_phase_3
            fi
            ;;
        2)
            run_phase_1
            ;;
        3)
            run_phase_2
            ;;
        4)
            setup_phase_3
            ;;
        5)
            test_phase_1
            ;;
        6)
            cleanup
            ;;
        7)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            ;;
    esac
done
