'''
This class implements an aggressive, self-managing strategy. It actively punishes components that cause a False
Positive by reducing their weight, making them less likely to be chosen in the future. It performs idle component
pruning not just on False Positives but also on True Positives, ensuring constant vigilance against stale
components. Both weight-based pruning and merging are included. Novelty is handled by creating a single
new Gaussian from a buffer, followed by a redundancy check. This class is designed to be highly adaptive
and constantly optimizing its own structure.
'''
# File: gmm_class_5.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2
from scipy.linalg import inv, det

class StreamingGMM:
    """
    Implements a streaming GMM with active punishment and comprehensive management.
    
    - Aging & Weight Pruning: Components are pruned if they are idle for too long OR if
      their mixture weight becomes negligibly small. This check happens frequently.
    - True Positives: The winning component is updated, and nearby components'
      idle counters are reset. Pruning checks are performed.
    - False Positives: The component responsible for the error is 'punished' by
      having its mixture weight reduced. Pruning checks are performed.
    - False Negatives: Novel points are buffered. When full, a single new Gaussian
      is trained and added.
    - Merging: After a new component is added, a check for redundancy is performed,
      and similar components are merged.
    """
    
    def __init__(self, dim, *points, kMax, 
                 # --- Hyperparameters ---
                 significance_level=0.05,
                 learning_rate=0.01,
                 neg_learning_rate=0.05, # Punishment rate for false positives
                 max_idle_iterations=300,
                 fn_buffer_size=20,
                 nearby_mahal_threshold=None,
                 merge_dist_threshold=0.5,
                 weight_prune_threshold=0.005): # Threshold for weight-based pruning
        
        self.dim = dim
        self.kMax = kMax
        self.omega = learning_rate
        self.delta = neg_learning_rate # Punishment rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.merge_dist_threshold = merge_dist_threshold
        self.weight_prune_threshold = weight_prune_threshold
        self.chi2_threshold = chi2.ppf(1 - significance_level, df=self.dim)
        
        self.nearby_mahal_threshold = nearby_mahal_threshold if nearby_mahal_threshold is not None else self.chi2_threshold * 1.5

        self.weights = np.array([]); self.means = np.empty((0, self.dim))
        self.covariances = np.empty((0, self.dim, self.dim)); self.idle_iterations = np.array([], dtype=int)
        self.fn_buffer = []

        data = np.array(points)
        if data.size > 0:
            self._batch_fit(data)
            print(f"Model initialized with {self.n_components} components.")

    @property
    def n_components(self): return len(self.weights)

    def _batch_fit(self, data):
        gmm = GaussianMixture(n_components=min(self.kMax, len(data)), covariance_type='full', random_state=0).fit(data)
        self.weights, self.means, self.covariances = gmm.weights_, gmm.means_, gmm.covariances_
        self.idle_iterations = np.zeros(self.n_components, dtype=int)

    def predict(self, point):
        if self.n_components == 0: return False, -1, np.inf
        sq_mahal_dists = np.zeros(self.n_components)
        for i in range(self.n_components):
            diff = point - self.means[i]
            try:
                cov_inv = inv(self.covariances[i] + np.eye(self.dim) * 1e-6)
                sq_mahal_dists[i] = diff.T @ cov_inv @ diff
            except np.linalg.LinAlgError: sq_mahal_dists[i] = np.inf
        min_dist_idx = np.argmin(sq_mahal_dists)
        is_inlier = sq_mahal_dists[min_dist_idx] < self.chi2_threshold
        return is_inlier, min_dist_idx, sq_mahal_dists

    def _prune_components(self):
        """Performs both idle-based and weight-based pruning."""
        if self.n_components == 0: return
        
        # Identify components to keep based on both criteria
        idle_ok = self.idle_iterations < self.max_idle_iterations
        weight_ok = self.weights >= self.weight_prune_threshold
        to_keep = idle_ok & weight_ok

        if np.all(to_keep): return
        
        pruned_count = self.n_components - np.sum(to_keep)
        if pruned_count > 0:
            self.weights = self.weights[to_keep]
            self.means = self.means[to_keep]
            self.covariances = self.covariances[to_keep]
            self.idle_iterations = self.idle_iterations[to_keep]
            if self.weights.size > 0: self.weights /= np.sum(self.weights)
            print(f"--- PRUNING: Removed {pruned_count} components (idle or low-weight). ---")

    def _bhattacharyya_distance(self, i, j):
        mu_i, C_i, mu_j, C_j = self.means[i], self.covariances[i], self.means[j], self.covariances[j]
        C_bar = (C_i + C_j) / 2
        try:
            C_bar_inv = inv(C_bar)
            det_C_bar, det_C_i, det_C_j = det(C_bar), det(C_i), det(C_j)
            if any(d <= 0 for d in [det_C_bar, det_C_i, det_C_j]): return np.inf
        except np.linalg.LinAlgError: return np.inf
        mu_diff = mu_i - mu_j
        term1 = 0.125 * mu_diff.T @ C_bar_inv @ mu_diff
        term2 = 0.5 * np.log(det_C_bar / np.sqrt(det_C_i * det_C_j))
        return term1 + term2

    def _merge_components(self):
        if self.n_components < 2: return
        min_dist, merge_pair = np.inf, None
        for i in range(self.n_components):
            for j in range(i + 1, self.n_components):
                dist = self._bhattacharyya_distance(i, j)
                if dist < min_dist: min_dist, merge_pair = dist, (i, j)
        
        if min_dist < self.merge_dist_threshold:
            print(f"--- MERGING: Found components {merge_pair} with distance {min_dist:.2f}. Merging. ---")
            i, j = merge_pair
            pi_i, mu_i, C_i, pi_j, mu_j, C_j = self.weights[i], self.means[i], self.covariances[i], self.weights[j], self.means[j], self.covariances[j]
            pi_merged = pi_i + pi_j
            mu_merged = (pi_i * mu_i + pi_j * mu_j) / pi_merged
            C_merged = (pi_i * (C_i + np.outer(mu_i-mu_merged, mu_i-mu_merged)) + pi_j * (C_j + np.outer(mu_j-mu_merged, mu_j-mu_merged))) / pi_merged
            
            indices_to_keep = [k for k in range(self.n_components) if k not in (i, j)]
            self.weights = np.append(self.weights[indices_to_keep], pi_merged)
            self.means = np.vstack((self.means[indices_to_keep], mu_merged))
            self.covariances = np.concatenate((self.covariances[indices_to_keep], [C_merged]), axis=0)
            self.idle_iterations = np.append(self.idle_iterations[indices_to_keep], min(self.idle_iterations[i], self.idle_iterations[j]))

    def update(self, point, feedback, prediction_result):
        was_predicted_inlier, j_star, all_dists = prediction_result
        if self.n_components > 0: self.idle_iterations += 1

        if was_predicted_inlier and feedback: # --- Case 1: True Positive ---
            self.idle_iterations[all_dists < self.nearby_mahal_threshold] = 0
            # Perform cleanup
            self._prune_components()
            # If pruning removed the component we were about to update, we must stop.
            if j_star >= self.n_components: return

            mu_old = self.means[j_star]
            self.means[j_star] = (1 - self.omega) * mu_old + self.omega * point
            residual = point - mu_old
            self.covariances[j_star] = (1 - self.omega) * self.covariances[j_star] + self.omega * np.outer(residual, residual)
            self.weights[j_star] = (1 - self.omega) * self.weights[j_star] + self.omega
            self.weights /= np.sum(self.weights)

        elif was_predicted_inlier and not feedback: # --- Case 2: False Positive ---
            print(f"--- PUNISHMENT: Reducing weight of component {j_star} for False Positive. ---")
            # Penalize the component by reducing its weight
            self.weights[j_star] *= (1 - self.delta)
            self.weights /= np.sum(self.weights) # Re-normalize
            # Perform cleanup
            self._prune_components()

        elif not was_predicted_inlier and feedback: # --- Case 4: False Negative ---
            self.fn_buffer.append(point)
            if len(self.fn_buffer) >= self.fn_buffer_size:
                print("--- FN Buffer full. Adding new Gaussian and checking for merges. ---")
                buffer_data = np.array(self.fn_buffer)
                new_gmm = GaussianMixture(n_components=1, covariance_type='full', random_state=0).fit(buffer_data)
                
                self.weights = np.append(self.weights, self.omega)
                self.means = np.vstack([self.means, new_gmm.means_[0]])
                self.covariances = np.concatenate([self.covariances, [new_gmm.covariances_[0]]], axis=0)
                self.idle_iterations = np.append(self.idle_iterations, 0)
                self.weights /= np.sum(self.weights)
                self.fn_buffer = []

                # Check for merges after adding the component
                self._merge_components()

if __name__ == '__main__':
    np.random.seed(0)
    data1 = np.random.randn(100, 2) + np.array([3, 3])
    data2 = np.random.randn(100, 2) + np.array([-3, -3])
    initial_data = np.vstack([data1, data2])

    # FIX: Pass dim positionally
    gmm = StreamingGMM(2, *initial_data, kMax=5, fn_buffer_size=15, 
                             merge_dist_threshold=1.0, neg_learning_rate=0.1, 
                             weight_prune_threshold=0.01)
                             
    print(f"\nInitial model has {gmm.n_components} components.")
    print("\n--- Streaming outliers (False Positives expected) ---")
    outlier_points = np.random.rand(10, 2) * 10 - 5
    for i, point in enumerate(outlier_points):
        pred_res = gmm.predict(point)
        gmm.update(point, feedback=False, prediction_result=pred_res)
    print(f"\nFinal model has {gmm.n_components} components with updated weights.")
    print(gmm.weights)