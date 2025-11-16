'''
This class extends the logic of the first class. It still uses idle-time pruning and buffered False Negatives. 
However, it operates on the assumption that a new concept might itself be complex and multi-modal. Therefore, 
when the novelty buffer is full, it trains a new Gaussian Mixture Model on the buffered data and imports all of
its discovered components into the main model. This allows for more flexible adaptation to complex new data 
patterns.
 '''
# File: gmm_class_2.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2
from scipy.linalg import inv

class StreamingGMM:
    """
    Implements a streaming GMM with a 'Full GMM from Buffer' strategy.
    
    - Aging: Components are pruned if they remain idle for too long.
    - True Positives: The winning component is updated, and nearby components'
      idle counters are reset.
    - False Negatives: Novel points are collected in a buffer. When the buffer is full,
      a new, multi-component GMM is trained on its contents. ALL components from this
      new GMM are then imported into the main model.
    """
    
    def __init__(self, dim, *points, kMax, 
                 # --- Hyperparameters ---
                 significance_level=0.05,
                 learning_rate=0.01,
                 max_idle_iterations=300,
                 fn_buffer_size=50,  # Buffer should be larger to support a GMM
                 fn_buffer_kMax=3,   # Max components for the GMM trained on the buffer
                 nearby_mahal_threshold=None):
        
        self.dim = dim
        self.kMax = kMax
        self.omega = learning_rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.fn_buffer_kMax = fn_buffer_kMax
        self.chi2_threshold = chi2.ppf(1 - significance_level, df=self.dim)
        
        self.nearby_mahal_threshold = nearby_mahal_threshold if nearby_mahal_threshold is not None else self.chi2_threshold * 1.5

        # --- Model State ---
        self.weights = np.array([])
        self.means = np.empty((0, self.dim))
        self.covariances = np.empty((0, self.dim, self.dim))
        self.idle_iterations = np.array([], dtype=int)
        self.fn_buffer = []

        # --- Initial Batch Training ---
        data = np.array(points)
        if data.size > 0:
            self._batch_fit(data)
            print(f"Model initialized with {self.n_components} components.")

    @property
    def n_components(self):
        return len(self.weights)

    def _batch_fit(self, data):
        """Finds the best initial GMM using BIC."""
        gmm = GaussianMixture(n_components=min(self.kMax, len(data)), covariance_type='full', random_state=0).fit(data)
        self.weights = gmm.weights_
        self.means = gmm.means_
        self.covariances = gmm.covariances_
        self.idle_iterations = np.zeros(self.n_components, dtype=int)

    def predict(self, point):
        """Predicts if a point is an inlier and finds the closest component."""
        if self.n_components == 0: return False, -1, np.inf
        
        sq_mahal_dists = np.zeros(self.n_components)
        for i in range(self.n_components):
            diff = point - self.means[i]
            try:
                cov_inv = inv(self.covariances[i] + np.eye(self.dim) * 1e-6)
                sq_mahal_dists[i] = diff.T @ cov_inv @ diff
            except np.linalg.LinAlgError:
                sq_mahal_dists[i] = np.inf

        min_dist_idx = np.argmin(sq_mahal_dists)
        min_dist = sq_mahal_dists[min_dist_idx]
        is_inlier = min_dist < self.chi2_threshold
        
        return is_inlier, min_dist_idx, sq_mahal_dists

    def _prune_idle_components(self):
        """Prunes components that have been idle for too long."""
        if self.n_components == 0: return
        
        to_keep = self.idle_iterations < self.max_idle_iterations
        if np.all(to_keep): return
        
        pruned_count = self.n_components - np.sum(to_keep)
        if pruned_count > 0:
            self.weights = self.weights[to_keep]
            self.means = self.means[to_keep]
            self.covariances = self.covariances[to_keep]
            self.idle_iterations = self.idle_iterations[to_keep]
            if self.weights.size > 0: self.weights /= np.sum(self.weights)
            print(f"--- AGING: Pruned {pruned_count} idle components. ---")

    def update(self, point, feedback, prediction_result):
        """Updates the model based on feedback."""
        was_predicted_inlier, j_star, all_dists = prediction_result
        
        if self.n_components > 0:
            self.idle_iterations += 1

        if was_predicted_inlier and feedback: # --- Case 1: True Positive ---
            nearby_components = all_dists < self.nearby_mahal_threshold
            self.idle_iterations[nearby_components] = 0
            
            mu_old = self.means[j_star]
            self.means[j_star] = (1 - self.omega) * mu_old + self.omega * point
            residual = point - mu_old
            self.covariances[j_star] = (1 - self.omega) * self.covariances[j_star] + self.omega * np.outer(residual, residual)
            self.weights[j_star] = (1 - self.omega) * self.weights[j_star] + self.omega
            self.weights /= np.sum(self.weights)

        elif was_predicted_inlier and not feedback: # --- Case 2: False Positive ---
            self._prune_idle_components()
            
        # --- Case 3: True Negative is implicitly handled (do nothing) ---

        elif not was_predicted_inlier and feedback: # --- Case 4: False Negative ---
            self.fn_buffer.append(point)
            print(f"False Negative detected. Buffer size: {len(self.fn_buffer)}/{self.fn_buffer_size}")
            
            if len(self.fn_buffer) >= self.fn_buffer_size:
                print(f"--- FN Buffer is full. Training a new GMM (k<={self.fn_buffer_kMax}) and importing its components. ---")
                buffer_data = np.array(self.fn_buffer)
                
                # Train a new GMM on the buffered points, finding the best k up to fn_buffer_kMax.
                lowest_bic, best_gmm = np.infty, None
                for k in range(1, self.fn_buffer_kMax + 1):
                    if len(buffer_data) < k: break # Can't have more components than points
                    gmm = GaussianMixture(n_components=k, covariance_type='full', random_state=0).fit(buffer_data)
                    bic = gmm.bic(buffer_data)
                    if bic < lowest_bic:
                        lowest_bic, best_gmm = bic, gmm
                
                if best_gmm is not None:
                    print(f"New GMM found {best_gmm.n_components} new components to add.")
                    # Calculate the total weight of the new components to be added
                    total_new_weight = self.omega * len(self.fn_buffer) / 100 # Heuristic for new weight
                    
                    # Scale down old weights to make room for new ones
                    self.weights *= (1 - total_new_weight)
                    
                    # Add all components from the newly trained GMM
                    for i in range(best_gmm.n_components):
                        # The weight of each new component is proportional to its weight in the sub-GMM
                        new_weight = total_new_weight * best_gmm.weights_[i]
                        
                        self.weights = np.append(self.weights, new_weight)
                        self.means = np.vstack([self.means, best_gmm.means_[i]])
                        self.covariances = np.concatenate([self.covariances, [best_gmm.covariances_[i]]], axis=0)
                        self.idle_iterations = np.append(self.idle_iterations, 0)
                
                # Clear the buffer
                self.fn_buffer = []

if __name__ == '__main__':
    np.random.seed(0)
    data1 = np.random.randn(100, 2) + np.array([3, 3])
    data2 = np.random.randn(100, 2) + np.array([-3, -3])
    initial_data = np.vstack([data1, data2])

    # FIX: Pass dim positionally
    gmm = StreamingGMM(2, *initial_data, kMax=5, fn_buffer_size=30, fn_buffer_kMax=2)
    
    print(f"\nInitial model has {gmm.n_components} components.")
    print("\n--- Streaming new bimodal cluster data (False Negatives expected) ---")
    new_cluster_1 = np.random.randn(20, 2) + np.array([5, -5])
    new_cluster_2 = np.random.randn(20, 2) + np.array([8, -8])
    new_points = np.vstack([new_cluster_1, new_cluster_2])
    np.random.shuffle(new_points)
    for i, point in enumerate(new_points):
        pred_res = gmm.predict(point)
        gmm.update(point, feedback=True, prediction_result=pred_res)
    print(f"\nFinal model has {gmm.n_components} components.")