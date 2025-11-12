import pathway as pw
from .features import compute_features
from .eligibility import load_config, is_eligible
from .model import load_model
import os
import pandas as pd

def main(product_type='home_loan', pathway_license_key=None):
    """
    Main pipeline orchestrator using Pathway for real-time stream processing.
    
    Args:
        product_type: Type of product to process (e.g., 'home_loan', 'life_insurance')
        pathway_license_key: Optional Pathway license key
    """

    if pathway_license_key:
        os.environ['PATHWAY_LICENSE_KEY'] = pathway_license_key
    
    # Load configuration and model
    config = load_config(product_type)
    model = load_model(product_type)
    
    # Prepare streaming data source
    base_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    processed_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
    os.makedirs(processed_path, exist_ok=True)
    
    # Create a combined stream dataset (merge transactions with client info)
    trans_path = os.path.join(base_path, 'trans.asc')
    client_path = os.path.join(base_path, 'client.asc')
    disp_path = os.path.join(base_path, 'disp.asc')
    account_path = os.path.join(base_path, 'account.asc')
    
    # Read and prepare stream data (limit for demo)
    print("Loading and preparing data...")
    trans_df = pd.read_csv(trans_path, sep=';', low_memory=False, nrows=500)
    client_df = pd.read_csv(client_path, sep=';')
    disp_df = pd.read_csv(disp_path, sep=';')
    account_df = pd.read_csv(account_path, sep=';')
    
    # Merge to get client_id for each transaction
    account_disp = account_df.merge(disp_df, on='account_id', how='left')
    account_disp = account_disp[account_disp['type'] == 'OWNER']  # Only owners
    stream_df = trans_df.merge(account_disp[['account_id', 'client_id', 'frequency', 'district_id']], 
                               on='account_id', how='left')
    stream_df = stream_df.merge(client_df[['client_id', 'birth_number', 'district_id']], 
                               on='client_id', how='left', suffixes=('', '_client'))
    
    # Use district_id from client if available, otherwise from account
    if 'district_id_client' in stream_df.columns:
        stream_df['district_id'] = stream_df['district_id_client'].fillna(stream_df.get('district_id', 0))
        stream_df = stream_df.drop(columns=['district_id_client'])
    
    # Fill NaN values for Pathway compatibility
    stream_df['client_id'] = stream_df['client_id'].fillna(0).astype(int)
    stream_df['district_id'] = stream_df['district_id'].fillna(0).astype(int)
    stream_df['birth_number'] = stream_df['birth_number'].fillna('').astype(str)
    
    # Ensure all required columns exist with proper defaults
    if 'frequency' not in stream_df.columns:
        stream_df['frequency'] = ''
    stream_df['frequency'] = stream_df['frequency'].fillna('').astype(str)
    
    if 'k_symbol' not in stream_df.columns:
        stream_df['k_symbol'] = ''
    stream_df['k_symbol'] = stream_df['k_symbol'].fillna('').astype(str)
    
    if 'bank' not in stream_df.columns:
        stream_df['bank'] = ''
    stream_df['bank'] = stream_df['bank'].fillna('').astype(str)
    
    if 'account' not in stream_df.columns:
        stream_df['account'] = ''
    stream_df['account'] = stream_df['account'].fillna('').astype(str)
    
    # Select and order columns for Pathway schema
    final_cols = ['trans_id', 'account_id', 'date', 'type', 'operation', 'amount', 'balance', 
                  'k_symbol', 'bank', 'account', 'client_id', 'district_id', 'frequency', 'birth_number']
    stream_df = stream_df[final_cols]
    
    # Create a temporary CSV for Pathway to read (use comma separator)
    stream_csv_path = os.path.join(processed_path, 'stream_input.csv')
    stream_df.to_csv(stream_csv_path, index=False, sep=',')
    
    print(f"Created stream input file with {len(stream_df)} rows")
    print("=" * 80)
    
    # Define Pathway table schema
    class InputSchema(pw.Schema):
        trans_id: int
        account_id: int
        date: int
        type: str
        operation: str
        amount: float
        balance: float
        k_symbol: str
        bank: str
        account: str
        client_id: int
        district_id: int
        frequency: str
        birth_number: str
    
    # Read CSV using Pathway (default separator is comma)
    table = pw.io.csv.read(
        stream_csv_path,
        schema=InputSchema,
        mode="static"  # Use static mode for batch processing (change to "streaming" for real-time)
    )
    
    # Process each row using Python UDF
    @pw.udf
    def process_event(
        client_id: int,
        account_id: int,
        balance: float,
        amount: float,
        trans_id: int,
        birth_number: str,
        district_id: int,
        type: str,
        operation: str,
    ) -> str:
        """Process event and return formatted output string."""
        row_dict = {
            'trans_id': trans_id,
            'account_id': account_id,
            'client_id': client_id if client_id > 0 else None,
            'balance': balance,
            'amount': amount,
            'birth_number': birth_number if birth_number else None,
            'district_id': district_id if district_id > 0 else None,
            'type': type,
            'operation': operation,
        }
        
        # Compute features
        feats = compute_features(row_dict, {})
        
        # Check eligibility
        eligible = is_eligible(feats, config)
        
        # Format output
        client_id_str = str(client_id) if client_id > 0 else 'N/A'
        
        if eligible:
            prediction_prob = model.predict(feats)
            prediction = model.predict_binary(feats)
            
            # Format features for display
            key_feats = {
                'age': feats.get('age', feats.get('estimated_age', 'N/A')),
                'balance': round(feats.get('balance', 0), 2),
                'income': round(feats.get('income', feats.get('estimated_income', 0)), 2),
                'activity_score': round(feats.get('activity_score', 0), 3),
            }
            
            status = "TARGET" if prediction else "SKIP (low score)"
            output = (
                f"{status}: Client {client_id_str} | "
                f"Features: {key_feats} | "
                f"Predicted(accept): {prediction} (prob: {prediction_prob:.3f})"
            )
        else:
            # Show why ineligible
            reasons = []
            age = feats.get('age', feats.get('estimated_age', 0))
            if config.get('min_age') and age < config.get('min_age', 0):
                reasons.append(f"age < {config.get('min_age')}")
            balance = feats.get('balance', 0)
            if config.get('min_balance') and balance < config.get('min_balance', 0):
                reasons.append(f"balance < {config.get('min_balance')}")
            income = feats.get('income', feats.get('estimated_income', 0))
            if config.get('min_income') and income < config.get('min_income', 0):
                reasons.append(f"income < {config.get('min_income')}")
            
            reason_str = ", ".join(reasons) if reasons else "config rules"
            output = (
                f"SKIP:   Client {client_id_str} | "
                f"Ineligible under {product_type} config ({reason_str})"
            )
        
        return output
    
    # Apply processing
    result = table.select(
        output=process_event(
            pw.this.client_id,
            pw.this.account_id,
            pw.this.balance,
            pw.this.amount,
            pw.this.trans_id,
            pw.this.birth_number,
            pw.this.district_id,
            pw.this.type,
            pw.this.operation,
        )
    )
    def print_output(key, row, time, is_addition):
        if is_addition:
            print(row['output'])
    
    pw.io.subscribe(result, print_output)
    
    # Also write to CSV for audit
    output_csv_path = os.path.join(processed_path, 'output.csv')
    pw.io.csv.write(result, output_csv_path)
    
    # Run the pipeline
    print(f"Starting Pathway pipeline for {product_type}...")
    print("=" * 80)
    pw.run()
    print("=" * 80)
    print(f"Pipeline completed. Results written to {output_csv_path}")
