# dataManager/redis_data_manager.py
"""
Redis Data Manager for Customer MASTERFILE
Provides centralized access to customer data stored in Redis
"""

import redis
import pandas as pd
import json
import pickle
from pathlib import Path
from typing import Optional, Dict, List
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))


class RedisDataManager:
    """Manages customer data in Redis with pandas DataFrame interface"""
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=1):
        """
        Initialize Redis connection for customer data
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number (using db=1 to separate from GMM models in db=0)
        """
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False  # Binary mode for pickle
        )
        self.data_key = "masterfile:data"
        self.metadata_key = "masterfile:metadata"
        self.customer_prefix = "customer:"
        
    def load_from_csv(self, csv_path: str, force_reload: bool = False) -> bool:
        """
        Load MASTERFILE.csv into Redis
        
        Args:
            csv_path: Path to MASTERFILE.csv
            force_reload: If True, reload even if data exists
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if data already exists
            if not force_reload and self.redis_client.exists(self.data_key):
                print(f"⚠ Data already exists in Redis. Use force_reload=True to overwrite.")
                return False
            
            print(f"Loading data from {csv_path}...")
            df = pd.read_csv(csv_path)
            
            # Store entire DataFrame as pickle
            serialized_df = pickle.dumps(df)
            self.redis_client.set(self.data_key, serialized_df)
            
            # Store metadata
            metadata = {
                'num_rows': str(len(df)),
                'num_columns': str(len(df.columns)),
                'columns': ','.join(df.columns),
                'csv_source': csv_path,
                'last_updated': str(pd.Timestamp.now())
            }
            self.redis_client.hset(self.metadata_key, mapping=metadata)
            
            # Also store individual customer records for fast lookup
            if 'customer_id' in df.columns:
                df_indexed = df.set_index('customer_id')
                for customer_id, row in df_indexed.iterrows():
                    customer_key = f"{self.customer_prefix}{customer_id}"
                    customer_data = row.to_dict()
                    self.redis_client.set(customer_key, pickle.dumps(customer_data))
                
                print(f"✓ Loaded {len(df)} customers into Redis")
                print(f"✓ Individual customer records indexed")
            else:
                print(f"✓ Loaded {len(df)} rows into Redis")
                print(f"⚠ No customer_id column found, individual indexing skipped")
            
            return True
            
        except Exception as e:
            print(f"✗ Error loading CSV to Redis: {e}")
            return False
    
    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Retrieve entire MASTERFILE as pandas DataFrame
        
        Returns:
            DataFrame or None if not found
        """
        try:
            serialized_df = self.redis_client.get(self.data_key)
            if serialized_df is None:
                print("✗ No data found in Redis. Please load data first.")
                return None
            
            df = pickle.loads(serialized_df)
            return df
            
        except Exception as e:
            print(f"✗ Error retrieving DataFrame from Redis: {e}")
            return None
    
    def get_customer(self, customer_id: str) -> Optional[Dict]:
        """
        Get single customer record by ID
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dictionary of customer data or None if not found
        """
        try:
            customer_key = f"{self.customer_prefix}{customer_id}"
            serialized_data = self.redis_client.get(customer_key)
            
            if serialized_data is None:
                return None
            
            return pickle.loads(serialized_data)
            
        except Exception as e:
            print(f"✗ Error retrieving customer {customer_id}: {e}")
            return None
    
    def get_customers(self, customer_ids: List[str]) -> pd.DataFrame:
        """
        Get multiple customers by IDs
        
        Args:
            customer_ids: List of customer IDs
            
        Returns:
            DataFrame with requested customers
        """
        try:
            customers = []
            for customer_id in customer_ids:
                customer_data = self.get_customer(customer_id)
                if customer_data:
                    customer_data['customer_id'] = customer_id
                    customers.append(customer_data)
            
            if not customers:
                return pd.DataFrame()
            
            return pd.DataFrame(customers)
            
        except Exception as e:
            print(f"✗ Error retrieving customers: {e}")
            return pd.DataFrame()
    
    def update_customer(self, customer_id: str, updates: Dict) -> bool:
        """
        Update customer record
        
        Args:
            customer_id: Customer ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            customer_key = f"{self.customer_prefix}{customer_id}"
            
            # Get existing data
            customer_data = self.get_customer(customer_id)
            if customer_data is None:
                print(f"✗ Customer {customer_id} not found")
                return False
            
            # Apply updates
            customer_data.update(updates)
            
            # Save back
            self.redis_client.set(customer_key, pickle.dumps(customer_data))
            
            # Also update the main DataFrame
            df = self.get_dataframe()
            if df is not None and 'customer_id' in df.columns:
                mask = df['customer_id'] == customer_id
                for key, value in updates.items():
                    if key in df.columns:
                        df.loc[mask, key] = value
                
                # Save updated DataFrame
                self.redis_client.set(self.data_key, pickle.dumps(df))
            
            return True
            
        except Exception as e:
            print(f"✗ Error updating customer {customer_id}: {e}")
            return False
    
    def get_metadata(self) -> Dict:
        """Get metadata about stored data"""
        try:
            metadata = self.redis_client.hgetall(self.metadata_key)
            decoded_metadata = {}
            for k, v in metadata.items():
                key = k.decode('utf-8') if isinstance(k, bytes) else k
                value = v.decode('utf-8') if isinstance(v, bytes) else v
                decoded_metadata[key] = value
            return decoded_metadata
        except Exception as e:
            print(f"✗ Error retrieving metadata: {e}")
            return {}
    
    def filter_dataframe(self, **kwargs) -> pd.DataFrame:
        """
        Filter DataFrame by column values
        
        Example:
            filter_dataframe(opted_car_loan=1, city_tier='tier1')
            
        Returns:
            Filtered DataFrame
        """
        df = self.get_dataframe()
        if df is None:
            return pd.DataFrame()
        
        for column, value in kwargs.items():
            if column in df.columns:
                df = df[df[column] == value]
        
        return df
    
    def clear_all(self):
        """Clear all customer data from Redis (use with caution!)"""
        try:
            # Delete main data
            self.redis_client.delete(self.data_key)
            self.redis_client.delete(self.metadata_key)
            
            # Delete all customer records
            cursor = 0
            deleted_count = 0
            while True:
                cursor, keys = self.redis_client.scan(
                    cursor=cursor,
                    match=f"{self.customer_prefix}*",
                    count=100
                )
                if keys:
                    self.redis_client.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break
            
            print(f"✓ Cleared all data: {deleted_count} customer records deleted")
            return True
            
        except Exception as e:
            print(f"✗ Error clearing data: {e}")
            return False
    
    def export_to_csv(self, csv_path: str) -> bool:
        """
        Export Redis data back to CSV
        
        Args:
            csv_path: Output CSV path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            df = self.get_dataframe()
            if df is None:
                return False
            
            df.to_csv(csv_path, index=False)
            print(f"✓ Exported {len(df)} rows to {csv_path}")
            return True
            
        except Exception as e:
            print(f"✗ Error exporting to CSV: {e}")
            return False


# Singleton instance for easy import
_data_manager = None

def get_data_manager(redis_host='localhost', redis_port=6379, redis_db=1):
    """Get or create singleton data manager"""
    global _data_manager
    if _data_manager is None:
        _data_manager = RedisDataManager(redis_host, redis_port, redis_db)
    return _data_manager
