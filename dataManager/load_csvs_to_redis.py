#!/usr/bin/env python3
# dataManager/load_csvs_to_redis.py
"""
Unified script to load all required CSV files into Redis
Run this once before starting the pipeline

Files loaded:
- MASTERFILE.csv -> Redis hash 'masterfile:data'
- loan_offers.csv -> Redis hash 'loan_offers:data'
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import redis
import pickle
import pandas as pd


def load_csv_to_redis(csv_path: Path, redis_client: redis.Redis, 
                      data_key: str, index_prefix: str = None,
                      index_column: str = None, force_reload: bool = False) -> bool:
    """
    Load a CSV file into Redis
    
    Args:
        csv_path: Path to CSV file
        redis_client: Redis client instance
        data_key: Redis key for storing the full DataFrame
        index_prefix: Optional prefix for individual record keys (e.g., 'customer:')
        index_column: Column to use as index for individual lookups
        force_reload: If True, overwrite existing data
    """
    try:
        # Check if data already exists
        if not force_reload and redis_client.exists(data_key):
            print(f"  ⚠ Data already exists for '{data_key}'. Use --force to reload.")
            return False
        
        # Load CSV
        print(f"  Loading {csv_path.name}...")
        df = pd.read_csv(csv_path)
        
        # Store entire DataFrame as pickle
        serialized_df = pickle.dumps(df)
        redis_client.set(data_key, serialized_df)
        
        # Store metadata
        metadata_key = data_key.replace(':data', ':metadata')
        metadata = {
            'num_rows': str(len(df)),
            'num_columns': str(len(df.columns)),
            'columns': ','.join(df.columns),
            'source_file': str(csv_path),
            'last_updated': str(pd.Timestamp.now())
        }
        redis_client.hset(metadata_key, mapping=metadata)
        
        # Index individual records if requested
        if index_prefix and index_column and index_column in df.columns:
            df_indexed = df.set_index(index_column)
            count = 0
            for record_id, row in df_indexed.iterrows():
                record_key = f"{index_prefix}{record_id}"
                record_data = row.to_dict()
                redis_client.set(record_key, pickle.dumps(record_data))
                count += 1
            print(f"  ✓ Loaded {len(df)} rows, indexed {count} individual records")
        else:
            print(f"  ✓ Loaded {len(df)} rows")
        
        return True
        
    except FileNotFoundError:
        print(f"  ✗ File not found: {csv_path}")
        return False
    except Exception as e:
        print(f"  ✗ Error loading {csv_path.name}: {e}")
        return False


def main():
    """Load all required CSV files to Redis"""
    parser = argparse.ArgumentParser(description='Load CSV files to Redis')
    parser.add_argument('--force', action='store_true', help='Force reload even if data exists')
    args = parser.parse_args()
    
    print("=" * 60)
    print("LOADING CSV FILES TO REDIS")
    print("=" * 60)
    
    # Redis configuration
    redis_host = 'localhost'
    redis_port = 6379
    redis_db = 1
    
    # Connect to Redis
    print(f"\n[Step 1] Connecting to Redis at {redis_host}:{redis_port} (db={redis_db})...")
    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False
        )
        redis_client.ping()
        print("✓ Redis connection successful")
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        print("\nPlease ensure Redis is running:")
        print("  sudo systemctl start redis")
        return False
    
    # Define files to load
    files_to_load = [
        {
            'name': 'MASTERFILE',
            'path': ROOT / 'MASTERFILE.csv',
            'data_key': 'masterfile:data',
            'index_prefix': 'customer:',
            'index_column': 'customer_id'
        },
        {
            'name': 'Loan Offers',
            'path': ROOT / 'carLoanPredictor' / 'loan_offers.csv',
            'data_key': 'loan_offers:data',
            'index_prefix': None,  # No individual indexing needed
            'index_column': None
        }
    ]
    
    # Load each file
    print(f"\n[Step 2] Loading CSV files...")
    results = {}
    
    for idx, file_config in enumerate(files_to_load, 1):
        print(f"\n  [{idx}/{len(files_to_load)}] {file_config['name']}:")
        success = load_csv_to_redis(
            csv_path=file_config['path'],
            redis_client=redis_client,
            data_key=file_config['data_key'],
            index_prefix=file_config['index_prefix'],
            index_column=file_config['index_column'],
            force_reload=args.force
        )
        results[file_config['name']] = success
    
    # Verification
    print(f"\n[Step 3] Verifying loaded data...")
    
    for file_config in files_to_load:
        data_key = file_config['data_key']
        serialized = redis_client.get(data_key)
        if serialized:
            df = pickle.loads(serialized)
            print(f"  ✓ {file_config['name']}: {len(df)} rows, {len(df.columns)} columns")
        else:
            print(f"  ✗ {file_config['name']}: Not found in Redis")
    
    # Summary
    print("\n" + "=" * 60)
    success_count = sum(1 for v in results.values() if v)
    total = len(results)
    
    if success_count == total:
        print(f"SUCCESS: All {total} files loaded to Redis!")
    else:
        print(f"PARTIAL: {success_count}/{total} files loaded to Redis")
    
    print("=" * 60)
    
    print("\nUsage in code:")
    print("  from dataManager.redis_data_manager import get_data_manager")
    print("  dm = get_data_manager()")
    print("  masterfile_df = dm.get_dataframe()  # MASTERFILE")
    print("")
    print("  # For loan offers:")
    print("  import redis, pickle")
    print("  r = redis.Redis(host='localhost', port=6379, db=1)")
    print("  loan_offers_df = pickle.loads(r.get('loan_offers:data'))")
    
    return all(results.values())


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
