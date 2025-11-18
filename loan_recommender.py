"""
Loan Recommender System
- Trains GMM on initial customer profiles
- Normalizes features to create portfolio vectors
- Clusters customers by loan types
- Detects portfolio changes and recommends loans
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime


class LoanRecommender:
    """
    Manages GMM clustering and loan recommendations based on portfolio similarity
    """
    
    def __init__(self, model_dir='models'):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        # Feature columns to use for portfolio vector (excluding identifiers and loan_type)
        self.feature_columns = [
            'total_transactions', 'num_income', 'num_expense',
            'total_income', 'total_expense', 'avg_income', 'avg_expense',
            'median_income', 'median_expense', 'std_income', 'std_expense',
            'max_income', 'max_expense', 'balance_current', 'balance_avg',
            'balance_min', 'balance_max', 'balance_volatility', 'net_cashflow',
            'income_expense_ratio', 'avg_transaction_size', 'transaction_frequency',
            'income_consistency', 'expense_consistency', 'spending_rate',
            'unique_categories', 'category_concentration'
        ]
        
        self.scaler = StandardScaler()
        self.gmm = None
        self.loan_type_mapping = {}
        self.customer_baseline_portfolios = {}  # Store original normalized portfolios
        self.customer_loan_types = {}  # Store customer's current loan type
        
    def train_initial_model(self, customer_profiles_path='data/customer_profiles.csv'):
        """
        Train GMM on initial customer profiles
        """
        print("=" * 70)
        print("Training Loan Recommendation Model")
        print("=" * 70)
        
        # Load customer profiles
        print("\n[1/5] Loading customer profiles...")
        df = pd.read_csv(customer_profiles_path)
        print(f"  ✓ Loaded {len(df)} customer profiles")
        print(f"  ✓ Loan types: {df['loan_type'].unique().tolist()}")
        
        # Extract features for clustering
        print("\n[2/5] Extracting and normalizing features...")
        X = df[self.feature_columns].fillna(0).values
        
        # Normalize features
        X_normalized = self.scaler.fit_transform(X)
        print(f"  ✓ Normalized {X_normalized.shape[1]} features for {X_normalized.shape[0]} customers")
        
        # Store baseline portfolios
        print("\n[3/5] Storing baseline portfolios...")
        for idx, row in df.iterrows():
            customer_id = int(row['customer_id'])
            self.customer_baseline_portfolios[customer_id] = X_normalized[idx]
            self.customer_loan_types[customer_id] = row['loan_type']
        print(f"  ✓ Stored baseline portfolios for {len(self.customer_baseline_portfolios)} customers")
        
        # Train GMM
        print("\n[4/5] Training Gaussian Mixture Model...")
        n_components = len(df['loan_type'].unique())
        self.gmm = GaussianMixture(
            n_components=n_components,
            covariance_type='full',
            random_state=42,
            max_iter=200,
            n_init=10
        )
        
        cluster_labels = self.gmm.fit_predict(X_normalized)
        print(f"  ✓ Trained GMM with {n_components} components")
        
        # Map clusters to loan types
        print("\n[5/5] Mapping clusters to loan types...")
        df['cluster'] = cluster_labels
        
        for cluster_id in range(n_components):
            cluster_customers = df[df['cluster'] == cluster_id]
            most_common_loan = cluster_customers['loan_type'].mode()[0]
            self.loan_type_mapping[cluster_id] = most_common_loan
            print(f"  Cluster {cluster_id} → {most_common_loan} ({len(cluster_customers)} customers)")
        
        # Save model
        self.save_model()
        
        print("\n" + "=" * 70)
        print("Model Training Complete!")
        print("=" * 70)
        print(f"\nModel saved to: {self.model_dir}/")
        print(f"  - gmm_model.pkl")
        print(f"  - scaler.pkl")
        print(f"  - loan_type_mapping.pkl")
        print(f"  - baseline_portfolios.pkl")
        
        return self
    
    def save_model(self):
        """Save trained model and associated data"""
        with open(f'{self.model_dir}/gmm_model.pkl', 'wb') as f:
            pickle.dump(self.gmm, f)
        
        with open(f'{self.model_dir}/scaler.pkl', 'wb') as f:
            pickle.dump(self.scaler, f)
        
        with open(f'{self.model_dir}/loan_type_mapping.pkl', 'wb') as f:
            pickle.dump(self.loan_type_mapping, f)
        
        with open(f'{self.model_dir}/baseline_portfolios.pkl', 'wb') as f:
            pickle.dump({
                'portfolios': self.customer_baseline_portfolios,
                'loan_types': self.customer_loan_types
            }, f)
    
    def load_model(self):
        """Load trained model and associated data"""
        try:
            with open(f'{self.model_dir}/gmm_model.pkl', 'rb') as f:
                self.gmm = pickle.load(f)
            
            with open(f'{self.model_dir}/scaler.pkl', 'rb') as f:
                self.scaler = pickle.load(f)
            
            with open(f'{self.model_dir}/loan_type_mapping.pkl', 'rb') as f:
                self.loan_type_mapping = pickle.load(f)
            
            with open(f'{self.model_dir}/baseline_portfolios.pkl', 'rb') as f:
                data = pickle.load(f)
                self.customer_baseline_portfolios = data['portfolios']
                self.customer_loan_types = data['loan_types']
            
            return True
        except FileNotFoundError:
            return False
    
    def create_portfolio_vector(self, features_dict):
        """
        Create normalized portfolio vector from features dictionary
        """
        # Create array in the correct order
        feature_values = []
        for col in self.feature_columns:
            feature_values.append(features_dict.get(col, 0.0))
        
        # Convert to numpy array and reshape
        X = np.array(feature_values).reshape(1, -1)
        
        # Normalize using trained scaler
        X_normalized = self.scaler.transform(X)
        
        return X_normalized[0]
    
    def calculate_similarity(self, portfolio1, portfolio2):
        """
        Calculate cosine similarity between two portfolio vectors
        Returns similarity as percentage (0-100)
        """
        similarity = cosine_similarity([portfolio1], [portfolio2])[0][0]
        # Convert to percentage
        similarity_percent = (similarity + 1) / 2 * 100  # Cosine similarity ranges from -1 to 1
        return similarity_percent
    
    def predict_loan_type(self, portfolio_vector):
        """
        Predict loan type for a given portfolio vector
        """
        cluster = self.gmm.predict([portfolio_vector])[0]
        return self.loan_type_mapping[cluster]
    
    def check_portfolio_change(self, customer_id, current_features, similarity_threshold=85.0):
        """
        Check if customer portfolio has changed significantly
        Returns (changed, similarity, recommended_loan_type, current_loan_type)
        """
        # Create current portfolio vector
        current_portfolio = self.create_portfolio_vector(current_features)
        
        # Check if this is a new customer
        if customer_id not in self.customer_baseline_portfolios:
            # New customer - add to baseline
            recommended_loan = self.predict_loan_type(current_portfolio)
            self.customer_baseline_portfolios[customer_id] = current_portfolio
            self.customer_loan_types[customer_id] = recommended_loan
            
            # Update model file
            self.save_model()
            
            return True, 0.0, recommended_loan, "NEW_CUSTOMER"
        
        # Existing customer - calculate similarity
        baseline_portfolio = self.customer_baseline_portfolios[customer_id]
        similarity = self.calculate_similarity(current_portfolio, baseline_portfolio)
        
        current_loan_type = self.customer_loan_types[customer_id]
        
        # Check if portfolio changed significantly
        if similarity < similarity_threshold:
            # Portfolio changed - recommend new loan type
            recommended_loan = self.predict_loan_type(current_portfolio)
            
            # Update baseline if recommendation is different
            if recommended_loan != current_loan_type:
                self.customer_baseline_portfolios[customer_id] = current_portfolio
                self.customer_loan_types[customer_id] = recommended_loan
                self.save_model()
                
                return True, similarity, recommended_loan, current_loan_type
        
        return False, similarity, current_loan_type, current_loan_type
    
    def update_for_new_customer(self, customer_id, features_dict):
        """
        Add new customer to the system and retrain GMM incrementally
        """
        portfolio = self.create_portfolio_vector(features_dict)
        recommended_loan = self.predict_loan_type(portfolio)
        
        self.customer_baseline_portfolios[customer_id] = portfolio
        self.customer_loan_types[customer_id] = recommended_loan
        
        # Save updated model
        self.save_model()
        
        return recommended_loan


def train_model_from_profiles():
    """
    Standalone function to train the model from customer profiles
    """
    recommender = LoanRecommender()
    recommender.train_initial_model('data/customer_profiles.csv')
    print("\n✓ Model training complete!")
    print("  You can now run the live feature processor.")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Loan Recommender - Model Training")
    print("=" * 70)
    print("\nThis script trains the GMM model on customer profiles.")
    print("Run this BEFORE starting the live feature processor.\n")
    
    # Check if customer profiles exist
    if not os.path.exists('data/customer_profiles.csv'):
        print("❌ Error: customer_profiles.csv not found!")
        print("   Please run: python generate_sample_data.py")
    else:
        train_model_from_profiles()