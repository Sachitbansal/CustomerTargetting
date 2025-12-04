import json
import numpy as np
import os
from sklearn.preprocessing import StandardScaler, OrdinalEncoder

from pathlib import Path
import sys

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))

from models.online_GMM_v1 import onlineGMMv1

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super(NumpyEncoder, self).default(obj)

def save_model_system(model, scaler, encoder, filepath):
    """
    Saves the GMM model, Scaler, and Encoder params to a JSON file.
    """
    # 1. Extract Scaler Params
    scaler_params = {
        'mean': scaler.mean_,
        'scale': scaler.scale_,
        'var': scaler.var_,
        'n_samples_seen': scaler.n_samples_seen_
    }

    # 2. Extract Encoder Params
    encoder_params = {
        'categories': [cat.tolist() for cat in encoder.categories_],
        'handle_unknown': encoder.handle_unknown,
        'unknown_value': encoder.unknown_value,
        'n_features_in': encoder.n_features_in_
    }

    # 3. Extract GMM Model Params
    gmm_params = {
        'num_dim': model.num_dim,
        'cat_dims': model.cat_dims,
        'kMax': model.kMax,
        'weights': model.weights,
        'means': model.means,
        'covariances': model.covariances,
        'idle_iterations': model.idle_iterations,
        'cat_probs': model.cat_probs,
        'exemplars': model.exemplars,
        'omega': model.omega,
        'delta': model.delta
    }

    master_payload = {
        'scaler': scaler_params,
        'encoder': encoder_params,
        'gmm': gmm_params
    }

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(master_payload, f, cls=NumpyEncoder, indent=4)
    print(f"Model system saved to {filepath}")

def load_model_system(filepath):
    """
    Loads JSON and reconstructs the GMM model, Scaler, and Encoder.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    # 1. Reconstruct Scaler
    scaler = StandardScaler()
    scaler.mean_ = np.array(data['scaler']['mean'])
    scaler.scale_ = np.array(data['scaler']['scale'])
    scaler.var_ = np.array(data['scaler']['var'])
    scaler.n_samples_seen_ = data['scaler']['n_samples_seen']

    # 2. Reconstruct Encoder - ROBUST FIX
    encoder_data = data['encoder']
    
    # Create encoder and fit on dummy data to initialize all internal attributes
    categories = [np.array(cat, dtype=object) for cat in encoder_data['categories']]
    n_features = len(categories)
    
    # Create a dummy dataset with one example per category
    dummy_data = []
    for cat_list in categories:
        if len(cat_list) > 0:
            dummy_data.append([cat_list[0]])  # Use first category
        else:
            dummy_data.append(['dummy'])
    
    # Transpose to get correct shape (1 sample, n_features)
    dummy_df = np.array(dummy_data).T
    
    # Initialize encoder with proper parameters
    encoder = OrdinalEncoder(
        handle_unknown=encoder_data.get('handle_unknown', 'use_encoded_value'),
        unknown_value=encoder_data.get('unknown_value', -1),
        encoded_missing_value=np.nan
    )
    
    # Fit on dummy data to initialize all internal attributes
    encoder.fit(dummy_df)
    
    # Now override with saved categories
    encoder.categories_ = categories
    encoder.n_features_in_ = encoder_data.get('n_features_in', n_features)
    
    # Ensure _missing_indices exists (it should after fit, but double-check)
    if not hasattr(encoder, '_missing_indices'):
        encoder._missing_indices = {}

    # 3. Reconstruct GMM
    gmm_data = data['gmm']
    model = onlineGMMv1(
        num_dim=gmm_data['num_dim'],
        cat_dims=gmm_data['cat_dims'],
        kMax=gmm_data['kMax']
    )
    
    # Restore internal state
    model.weights = np.array(gmm_data['weights'])
    model.means = np.array(gmm_data['means'])
    model.covariances = np.array(gmm_data['covariances'])
    model.idle_iterations = np.array(gmm_data['idle_iterations'])
    model.omega = gmm_data['omega']
    model.delta = gmm_data['delta']
    model.exemplars = gmm_data['exemplars']
    
    # Restore Cat Probs
    model.cat_probs = []
    for comp_probs in gmm_data['cat_probs']:
        reconstructed_comp = [np.array(dim_prob) for dim_prob in comp_probs]
        model.cat_probs.append(reconstructed_comp)

    return model, scaler, encoder