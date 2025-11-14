import pandas as pd
import os
from datetime import datetime

# Load lookup tables for enrichment (cached)
_lookup_cache = None

def _load_lookup_tables():
    """Load lookup tables for enrichment."""
    global _lookup_cache
    if _lookup_cache is not None:
        return _lookup_cache
    
    # Initialize cache
    _lookup_cache = {}
    
    base_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    
    try:
        # Load client data
        client_df = pd.read_csv(os.path.join(base_path, 'client.asc'), sep=';')
        _lookup_cache['client'] = client_df.set_index('client_id').to_dict('index')
        
        # Load account data
        account_df = pd.read_csv(os.path.join(base_path, 'account.asc'), sep=';')
        _lookup_cache['account'] = account_df.set_index('account_id').to_dict('index')
        
        # Load district data
        district_df = pd.read_csv(os.path.join(base_path, 'district.asc'), sep=';')
        district_df.rename(columns={'A1': 'district_id'}, inplace=True)
        _lookup_cache['district'] = district_df.set_index('district_id').to_dict('index')
        
        # Load transaction aggregates (pre-computed for demo)
        trans_df = pd.read_csv(os.path.join(base_path, 'trans.asc'), sep=';', low_memory=False)
        trans_agg = trans_df.groupby('account_id').agg({
            'amount': ['sum', 'mean', 'count'],
            'balance': 'last'
        }).reset_index()
        trans_agg.columns = ['account_id', 'total_amount', 'avg_amount', 'txn_count', 'last_balance']
        _lookup_cache['trans_agg'] = trans_agg.set_index('account_id').to_dict('index')
        
    except Exception as e:
        print(f"Warning: Could not load lookup tables: {e}")
        _lookup_cache = {
            'client': {},
            'account': {},
            'district': {},
            'trans_agg': {}
        }
    
    return _lookup_cache

def _parse_birth_number(birth_number_str):
    """Parse Czech birth number format to extract age."""
    try:
        birth_str = str(birth_number_str).strip().strip('"')
        if len(birth_str) < 6:
            return None
        
        year = int(birth_str[:2])
        month = int(birth_str[2:4])
        day = int(birth_str[4:6])
        
        # Adjust for century (simplified)
        if year < 50:
            year += 2000
        else:
            year += 1900
        
        # Adjust month for women (add 50)
        if month > 12:
            month -= 50
        
        birth_date = datetime(year, month, day)
        age = (datetime.now() - birth_date).days // 365
        return age
    except:
        return None

def compute_features(row, extra_context=None):
    """
    Compute derived features from a transaction/application row with enrichment.
    
    Args:
        row: Dictionary or Pathway row with transaction/application data
        extra_context: Additional context for feature computation
        
    Returns:
        Dictionary of computed features
    """
    if extra_context is None:
        extra_context = {}
    
    # Load lookup tables
    lookups = _load_lookup_tables()
    
    # Start with base features from row
    features = dict(row)
    
    # Extract client_id and account_id
    client_id = row.get('client_id') or row.get('client_id')
    account_id = row.get('account_id')
    
    # Enrich with client data
    if client_id and client_id in lookups.get('client', {}):
        client_data = lookups['client'][client_id]
        features['birth_number'] = client_data.get('birth_number')
        features['district_id'] = client_data.get('district_id')
        
        # Compute age from birth number
        if features.get('birth_number'):
            age = _parse_birth_number(features['birth_number'])
            if age:
                features['age'] = age
                features['estimated_age'] = age
    
    # Enrich with account data
    if account_id and account_id in lookups.get('account', {}):
        account_data = lookups['account'][account_id]
        features['account_frequency'] = account_data.get('frequency')
        features['account_date'] = account_data.get('date')
    
    # Enrich with transaction aggregates
    if account_id and account_id in lookups.get('trans_agg', {}):
        trans_data = lookups['trans_agg'][account_id]
        features['total_transaction_amount'] = trans_data.get('total_amount', 0)
        features['avg_transaction_amount'] = trans_data.get('avg_amount', 0)
        features['txn_count'] = trans_data.get('txn_count', 0)
        features['last_balance'] = trans_data.get('last_balance', 0)
    
    # Use balance from row or last_balance
    balance = row.get('balance') or features.get('last_balance', 0)
    features['balance'] = balance
    
    # Compute derived features
    if features.get('balance') and features.get('txn_count'):
        features['avg_balance'] = features['balance'] / max(features['txn_count'], 1)
    else:
        features['avg_balance'] = features.get('balance', 0)
    
    # Estimate income from transaction patterns (simplified heuristic)
    if features.get('avg_transaction_amount'):
        # Rough estimate: monthly income ~ 3x average transaction
        features['estimated_income'] = features['avg_transaction_amount'] * 3 * 12
        features['income'] = features['estimated_income']
    else:
        features['estimated_income'] = 0
        features['income'] = 0
    
    # Enrich with district data for income estimation
    district_id = features.get('district_id')
    if district_id and district_id in lookups.get('district', {}):
        district_data = lookups['district'][district_id]
        # A11 is average salary in district
        if 'A11' in district_data:
            features['district_avg_salary'] = district_data['A11']
            # Use district average if no transaction-based estimate
            if not features.get('income'):
                features['income'] = district_data['A11']
                features['estimated_income'] = district_data['A11']
    
    # Behavioral scores
    if features.get('txn_count', 0) > 0:
        features['activity_score'] = min(features['txn_count'] / 100.0, 1.0)  # Normalized
    else:
        features['activity_score'] = 0.0
    
    # Employment status (simplified: assume employed if regular transactions)
    features['has_employment'] = features.get('txn_count', 0) > 10
    features['employment_status'] = features.get('has_employment', False)
    
    # Default status (simplified: check if balance is negative)
    features['has_default'] = features.get('balance', 0) < 0
    features['previous_default'] = features.get('has_default', False)
    
    return features
