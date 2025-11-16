'''
This class implements a conservative adaptation strategy. It uses an idle-time counter (t_j) to prune stale components. When it encounters novel data (False
 Negatives), it collects these points in a buffer. Once enough evidence is gathered, it models this new data as a single new Gaussian
 and adds it to the existing model. This approach is stable but assumes new concepts are unimodal.
'''
# File: gmm_class_1.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2
from scipy.linalg import inv

class StreamingGMM:
    """
    Implements a streaming GMM with a 'Single Gaussian from Buffer' strategy.
    
    - Aging: Components are pruned if they remain idle for too long.
    - True Positives: The winning component is updated. All components that were
      'close' to the point have their idle counters reset.
    - False Negatives: Novel points are collected in a buffer. When the buffer is full,
      a SINGLE new Gaussian is trained on its contents and added to the model.
    """
    
    def __init__(self, dim, *points, kMax, 
                 # --- Hyperparameters ---
                 significance_level=0.05,
                 learning_rate=0.01,
                 max_idle_iterations=300,
                 fn_buffer_size=20,
                 nearby_mahal_threshold=None):
        
        self.dim = dim
        self.kMax = kMax
        self.omega = learning_rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.chi2_threshold = chi2.ppf(1 - significance_level, df=self.dim)
        
        # If no threshold is given, set it to 1.5x the chi2 threshold.
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
        
        # Increment all idle counters first. This happens every time feedback is received.
        if self.n_components > 0:
            self.idle_iterations += 1

        if was_predicted_inlier and feedback: # --- Case 1: True Positive ---
            # Reset idle counters for ALL components that were reasonably close to the point.
            nearby_components = all_dists < self.nearby_mahal_threshold
            self.idle_iterations[nearby_components] = 0
            
            # Update the parameters of the WINNING (closest) component.
            mu_old = self.means[j_star]
            self.means[j_star] = (1 - self.omega) * mu_old + self.omega * point
            residual = point - mu_old
            self.covariances[j_star] = (1 - self.omega) * self.covariances[j_star] + self.omega * np.outer(residual, residual)
            self.weights[j_star] = (1 - self.omega) * self.weights[j_star] + self.omega
            self.weights /= np.sum(self.weights)

        elif was_predicted_inlier and not feedback: # --- Case 2: False Positive ---
            # Do nothing to the model parameters, but this is an opportunity to clean up.
            self._prune_idle_components()
            
        # --- Case 3: True Negative is implicitly handled (do nothing) ---

        elif not was_predicted_inlier and feedback: # --- Case 4: False Negative ---
            self.fn_buffer.append(point)
            print(f"False Negative detected. Buffer size: {len(self.fn_buffer)}/{self.fn_buffer_size}")
            
            if len(self.fn_buffer) >= self.fn_buffer_size:
                print("--- FN Buffer is full. Training and adding a new single Gaussian. ---")
                buffer_data = np.array(self.fn_buffer)
                
                # Train a single new Gaussian on the buffered points.
                new_gmm = GaussianMixture(n_components=1, covariance_type='full', random_state=0).fit(buffer_data)
                
                # Add its parameters to the main model.
                self.weights = np.append(self.weights, self.omega) # Start with a small weight
                self.means = np.vstack([self.means, new_gmm.means_[0]])
                self.covariances = np.concatenate([self.covariances, [new_gmm.covariances_[0]]], axis=0)
                self.idle_iterations = np.append(self.idle_iterations, 0)
                
                # Re-normalize all weights and clear the buffer.
                self.weights /= np.sum(self.weights)
                self.fn_buffer = []

if __name__ == '__main__':
    np.random.seed(0)
    data1 = np.random.randn(100, 2) + np.array([3, 3])
    data2 = np.random.randn(100, 2) + np.array([-3, -3])
    initial_data = np.vstack([data1, data2])
    
    # FIX: Pass dim positionally
    gmm = StreamingGMM(2, *initial_data, kMax=5, fn_buffer_size=10)
    
    print(f"\nInitial model has {gmm.n_components} components.")
    print("\n--- Streaming new cluster data (False Negatives expected) ---")
    new_cluster_points = np.random.randn(15, 2) + np.array([5, -5])
    for i, point in enumerate(new_cluster_points):
        pred_res = gmm.predict(point)
        gmm.update(point, feedback=True, prediction_result=pred_res)
    print(f"\nFinal model has {gmm.n_components} components.")