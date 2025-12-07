#!/bin/bash

# PATH TO YOUR VENV ACTIVATE
VENV_PATH="$HOME/Documents/VSCProjects/TargettedCalling/venv/bin/activate"

# FUNCTION TO OPEN TERMINAL + ACTIVATE VENV + RUN SCRIPT
run_in_terminal() {
    gnome-terminal -- bash -c "
        source $VENV_PATH;
        echo 'Running: $1';
        python3 $1;
        exec bash
    "
}

# run_in_terminal "carLoanPredictor/init_car_trainer.py"
run_in_terminal "carLoanPredictor/run_predictor.py"
run_in_terminal "carLoanFeedback/run_feedback.py"
run_in_terminal "dataUpdater/run_detector_publisher.py"

run_in_terminal "report_gen/llm_gen.py"
run_in_terminal "report_gen/read_pred.py"


run_in_terminal "leadPublisher/run_publisher.py"
run_in_terminal "transactionPublisher/run_publisher.py"
run_in_terminal "carLoanPredictor/tester.py"
