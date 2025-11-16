'''
This class adds a layer of self-cleanup to the "Single Gaussian from Buffer" strategy. When a new Gaussian is created from the novelty buffer, the model immediately runs a component merging check. This is crucial for preventing the model from becoming bloated with redundant, overlapping components, which can happen if the new concept is close to an existing one. It keeps the model parsimonious and efficient.
'''
# File: gmm_class_3.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2
from scipy.linalg import inv, det

class StreamingGMM:
    """
    Implements a streaming GMM with 'Single Gaussian from Buffer' and merging.
    
    - Aging: Components are pruned if they remain idle for too long.
    - True Positives: The winning component is updated, and nearby components'
      idle counters are reset.
    - False Negatives: Novel points are collected in a buffer. When the buffer is full,
      a single new Gaussian is trained and added to the model.
    - Merging: After adding a new component, a check for redundant/similar
      components is performed, and any that are too close are merged.
    """
    
    def __init__(self, dim, *points, kMax, 
                 # --- Hyperparameters ---
                 significance_level=0.05,
                 learning_rate=0.01,
                 max_idle_iterations=300,
                 fn_buffer_size=20,
                 nearby_mahal_threshold=None,
                 merge_dist_threshold=0.5): # Threshold for merging
        
        self.dim = dim
        self.kMax = kMax
        self.omega = learning_rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.merge_dist_threshold = merge_dist_threshold
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
        gmm = GaussianMixture(n_components=min(self.kMax, len(data)), covariance_type='full', random_state=0).fit(data)
        self.weights = gmm.weights_
        self.means = gmm.means_
        self.covariances = gmm.covariances_
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

    def _prune_idle_components(self):
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

    def _bhattacharyya_distance(self, i, j):
        """Calculates the similarity between two Gaussian components."""
        mu_i, C_i = self.means[i], self.covariances[i]
        mu_j, C_j = self.means[j], self.covariances[j]
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
        """Finds and merges the most similar pair of components if they are close enough."""
        if self.n_components < 2: return
        
        min_dist, merge_pair = np.inf, None
        for i in range(self.n_components):
            for j in range(i + 1, self.n_components):
                dist = self._bhattacharyya_distance(i, j)
                if dist < min_dist:
                    min_dist, merge_pair = dist, (i, j)
        
        if min_dist < self.merge_dist_threshold:
            print(f"--- MERGING: Found components {merge_pair} with distance {min_dist:.2f} < {self.merge_dist_threshold}. Merging. ---")
            i, j = merge_pair
            pi_i, mu_i, C_i = self.weights[i], self.means[i], self.covariances[i]
            pi_j, mu_j, C_j = self.weights[j], self.means[j], self.covariances[j]
            
            pi_merged = pi_i + pi_j
            mu_merged = (pi_i * mu_i + pi_j * mu_j) / pi_merged
            C_merged = (pi_i * (C_i + np.outer(mu_i - mu_merged, mu_i - mu_merged)) +
                        pi_j * (C_j + np.outer(mu_j - mu_merged, mu_j - mu_merged))) / pi_merged
            
            # Remove the old components and add the new one
            indices_to_keep = [k for k in range(self.n_components) if k not in (i, j)]
            self.weights = np.append(self.weights[indices_to_keep], pi_merged)
            self.means = np.vstack((self.means[indices_to_keep], mu_merged))
            self.covariances = np.concatenate((self.covariances[indices_to_keep], [C_merged]), axis=0)
            # New component inherits the lowest idle count of its parents
            self.idle_iterations = np.append(self.idle_iterations[indices_to_keep], 
                                             min(self.idle_iterations[i], self.idle_iterations[j]))

    def update(self, point, feedback, prediction_result):
        was_predicted_inlier, j_star, all_dists = prediction_result
        if self.n_components > 0: self.idle_iterations += 1

        if was_predicted_inlier and feedback: # True Positive
            self.idle_iterations[all_dists < self.nearby_mahal_threshold] = 0
            mu_old = self.means[j_star]
            self.means[j_star] = (1 - self.omega) * mu_old + self.omega * point
            residual = point - mu_old
            self.covariances[j_star] = (1 - self.omega) * self.covariances[j_star] + self.omega * np.outer(residual, residual)
            self.weights[j_star] = (1 - self.omega) * self.weights[j_star] + self.omega
            self.weights /= np.sum(self.weights)

        elif was_predicted_inlier and not feedback: # False Positive
            self._prune_idle_components()

        elif not was_predicted_inlier and feedback: # False Negative
            self.fn_buffer.append(point)
            print(f"False Negative detected. Buffer size: {len(self.fn_buffer)}/{self.fn_buffer_size}")
            
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

                # --- NEW STEP: Check for merges after adding the component ---
                self._merge_components()

if __name__ == '__main__':
    np.random.seed(0)
    data1 = np.random.randn(100, 2) + np.array([3, 3])
    data2 = np.random.randn(100, 2) + np.array([-3, -3])
    initial_data = np.vstack([data1, data2])
    
    # FIX: Pass dim positionally
    gmm = StreamingGMM(2, *initial_data, kMax=5, fn_buffer_size=15, merge_dist_threshold=1.0)
    
    print(f"\nInitial model has {gmm.n_components} components.")
    print("\n--- Streaming new, nearby cluster data ---")
    new_cluster_points = np.random.randn(20, 2) + np.array([4, 4])
    for i, point in enumerate(new_cluster_points):
        pred_res = gmm.predict(point)
        gmm.update(point, feedback=True, prediction_result=pred_res)
    print(f"\nFinal model has {gmm.n_components} components.")