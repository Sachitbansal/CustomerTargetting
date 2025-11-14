# TargettedCalling - Project Structure

## Overview
This project implements a real-time targeting pipeline using Pathway for stream processing and machine learning models for predicting customer targeting.

## Directory Structure

```
TargettedCalling/
├── configs/                          # Configuration files
│   └── product_config.yaml          # Product-specific eligibility rules
│
├── data/                            # Data directory
│   ├── raw/                        # Raw input data files
│   └── processed/                  # Processed output files
│
├── src/                             # Source code
│   ├── __init__.py                 # Main package initialization
│   │
│   ├── data_preprocessing/         # Data preprocessing modules
│   │   ├── __init__.py
│   │   └── split_data.py          # Train/test data splitting
│   │
│   ├── model_training/             # Model training modules
│   │   ├── __init__.py
│   │   ├── train_embedding_model.py  # Train embedding model
│   │   ├── evaluate_model.py         # Evaluate model performance
│   │   ├── embedding_model.py        # Embedding model architecture
│   │   └── model.py                  # Model loading and inference
│   │
│   ├── utils/                      # Utility functions
│   │   ├── __init__.py
│   │   ├── features.py            # Feature computation
│   │   └── eligibility.py         # Eligibility checking
│   │
│   └── pathway_pipeline.py        # Main Pathway streaming pipeline
│
├── run.py                          # Entry point for Pathway pipeline
├── train_and_evaluate.py          # Entry point for model training
└── requirements.txt                # Python dependencies
```

## Module Descriptions

### Data Preprocessing (`src/data_preprocessing/`)
Contains code for preprocessing and preparing data for model training.

- **split_data.py**: Splits raw data into train and test sets, handles data merging and feature aggregation

### Model Training (`src/model_training/`)
Contains all model training, evaluation, and inference code.

- **train_embedding_model.py**: Trains the embedding-based similarity model
- **evaluate_model.py**: Evaluates model performance on test data
- **embedding_model.py**: Neural network architecture for user embeddings
- **model.py**: Model loading utilities and wrapper classes

### Utils (`src/utils/`)
Contains utility functions used across the codebase.

- **features.py**: Feature computation and enrichment functions
- **eligibility.py**: Business rule checking for customer eligibility

### Pathway Pipeline (`src/`)
The main streaming pipeline code that uses Pathway for real-time processing.

- **pathway_pipeline.py**: Main pipeline orchestration, stream processing logic

## Entry Points

### 1. Pathway Pipeline (Real-time Processing)
```bash
python run.py [product_type]
```
Runs the real-time Pathway pipeline for targeted calling.

### 2. Model Training & Evaluation
```bash
python train_and_evaluate.py
```
Trains the embedding model and evaluates its performance.

## Import Structure

The reorganized structure uses proper Python package imports:

```python
# From root scripts
from src.pathway_pipeline import main
from src.model_training.train_embedding_model import train_model
from src.data_preprocessing.split_data import split_train_test

# From within src packages
from ..utils.features import compute_features
from ..model_training.model import load_model
```

## Key Features

1. **Modular Design**: Code is organized by function (data preprocessing, model training, utilities)
2. **Clean Separation**: Pathway pipeline code is separate from model training code
3. **Easy Navigation**: Clear folder structure makes it easy to find specific functionality
4. **Maintainable**: Each module has a single, well-defined responsibility

## Running the Project

### Training Workflow
1. Data is split into train/test sets (`data_preprocessing/split_data.py`)
2. Embedding model is trained (`model_training/train_embedding_model.py`)
3. Model is evaluated on test data (`model_training/evaluate_model.py`)

### Inference Workflow
1. Pathway pipeline loads the trained model (`pathway_pipeline.py`)
2. Stream data is processed in real-time
3. Features are computed for each event (`utils/features.py`)
4. Eligibility is checked (`utils/eligibility.py`)
5. Model makes predictions for eligible customers
6. Results are output to console and CSV

## Development Guidelines

- **Data Preprocessing**: Add new preprocessing scripts to `src/data_preprocessing/`
- **Model Training**: Add new models or training scripts to `src/model_training/`
- **Utilities**: Add shared utility functions to `src/utils/`
- **Pipeline**: Modify streaming logic in `src/pathway_pipeline.py`
