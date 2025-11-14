import yaml
import os

def load_config(product_type='home_loan'):
    """Load product configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'configs', 'product_config.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    # Return config for the specific product type
    return config

def is_eligible(features, config):
    """
    Check if a candidate is eligible based on business rules in config.
    
    Args:
        features: Dictionary of computed features
        config: Product configuration dictionary
        
    Returns:
        bool: True if eligible, False otherwise
    """
    # Extract age from birth_number or features
    age = features.get('age', features.get('estimated_age', 0))
    if config.get('min_age') and age < config.get('min_age', 0):
        return False
    if config.get('max_age') and age > config.get('max_age', 999):
        return False
    
    # Check balance
    balance = features.get('balance', features.get('avg_balance', 0))
    if config.get('min_balance') and balance < config.get('min_balance', 0):
        return False
    
    # Check income
    income = features.get('income', features.get('estimated_income', 0))
    if config.get('min_income') and income < config.get('min_income', 0):
        return False
    
    # Check employment
    if config.get('employment_required') == 'yes':
        employment = features.get('employment_status', features.get('has_employment', False))
        if not employment:
            return False
    
    # Check previous defaults
    if config.get('previous_default') == 'no':
        has_default = features.get('has_default', features.get('previous_default', False))
        if has_default:
            return False
    
    return True
