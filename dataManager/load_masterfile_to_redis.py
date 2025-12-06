# dataManager/load_masterfile_to_redis.py
"""
One-time script to load MASTERFILE.csv into Redis
Run this once before using the Redis data manager
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from dataManager.redis_data_manager import get_data_manager


def main():
    """Load MASTERFILE.csv into Redis"""
    print("=" * 60)
    print("LOADING MASTERFILE TO REDIS")
    print("=" * 60)
    
    # Configuration
    csv_path = ROOT / "MASTERFILE.csv"
    redis_host = 'localhost'
    redis_port = 6379
    redis_db = 1  # Using db=1 for customer data, db=0 for GMM models
    
    # Check if CSV exists
    if not csv_path.exists():
        print(f"✗ Error: {csv_path} not found!")
        print("\nPlease ensure MASTERFILE.csv exists in the project root.")
        print("Generate it using:")
        print("  cd experiment7_pathway")
        print("  python create_masterfile.py")
        print("  cd ..")
        return False
    
    # Get data manager
    print(f"\n[1/3] Connecting to Redis at {redis_host}:{redis_port} (db={redis_db})...")
    data_manager = get_data_manager(redis_host, redis_port, redis_db)
    
    try:
        data_manager.redis_client.ping()
        print("✓ Redis connection successful")
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        print("\nPlease ensure Redis is running:")
        print("  sudo systemctl start redis")
        return False
    
    # Load data
    print(f"\n[2/3] Loading data from {csv_path}...")
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Force reload even if data exists')
    args = parser.parse_args()
    
    success = data_manager.load_from_csv(str(csv_path), force_reload=args.force)
    
    if not success:
        if not args.force:
            print("\nData already exists in Redis. Use --force to reload.")
        return False
    
    # Verify
    print(f"\n[3/3] Verifying data...")
    metadata = data_manager.get_metadata()
    
    if metadata:
        print(f"✓ Data verification successful")
        print(f"\nMetadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
        
        # Test retrieval
        df = data_manager.get_dataframe()
        if df is not None:
            print(f"\n✓ Successfully loaded DataFrame with {len(df)} rows")
            print(f"  Columns: {', '.join(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")
            
            # Test individual customer lookup
            if 'customer_id' in df.columns:
                sample_customer_id = df['customer_id'].iloc[0]
                customer_data = data_manager.get_customer(sample_customer_id)
                if customer_data:
                    print(f"✓ Individual customer lookup working (tested: {sample_customer_id})")
        
        print("\n" + "=" * 60)
        print("SUCCESS: MASTERFILE loaded to Redis!")
        print("=" * 60)
        print("\nYou can now use RedisDataManager in your code:")
        print("  from dataManager import get_data_manager")
        print("  data_manager = get_data_manager()")
        print("  df = data_manager.get_dataframe()")
        
        return True
    else:
        print("✗ Data verification failed")
        return False


if __name__ == '__main__':
    import argparse
    success = main()
    sys.exit(0 if success else 1)
