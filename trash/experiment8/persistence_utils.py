# persistence_utils.py
import json
import numpy as np
import os
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
from streaming_hybrid_advanced import StreamingHybridAdvanced

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
    # categories_ is a list of arrays, convert to list of lists
    encoder_params = {
        'categories': [cat.tolist() for cat in encoder.categories_]
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

    # 2. Reconstruct Encoder
    encoder = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
    # We need to manually set the categories_ attribute
    encoder.categories_ = [np.array(cat, dtype=object) for cat in data['encoder']['categories']]
    # Dummy fit to initialize internal attributes if needed, though usually categories_ is enough for transform
    # We verify simple transform later.

    # 3. Reconstruct GMM
    gmm_data = data['gmm']
    model = StreamingHybridAdvanced(
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
    model.exemplars = gmm_data['exemplars'] # List of lists
    
    # Restore Cat Probs (List of Lists of Arrays)
    model.cat_probs = []
    for comp_probs in gmm_data['cat_probs']:
        reconstructed_comp = [np.array(dim_prob) for dim_prob in comp_probs]
        model.cat_probs.append(reconstructed_comp)

    return model, scaler, encoder