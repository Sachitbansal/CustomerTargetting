'''
This class represents a powerful strategy for adapting to complex new concepts. When the novelty buffer fills, it trains a new GMM on the buffered data and imports all of its discovered components. Crucially, it then immediately triggers a component merging phase. This allows the model to learn multi-modal new concepts while also ensuring that the newly imported components are efficiently integrated, merging with each other or with pre-existing components if they are too similar. This prevents redundancy and keeps the overall model compact.
'''
# File: gmm_class_4.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2
from scipy.linalg import inv, det

class StreamingGMM:
    """
    Implements a streaming GMM with 'Full GMM from Buffer' and merging.
    
    - Aging: Components are pruned if they remain idle for too long.
    - True Positives: The winning component is updated, and nearby components'
      idle counters are reset.
    - False Negatives: Novel points are collected in a buffer. When the buffer is full,
      a new GMM is trained on the data, and all its components are imported.
    - Merging: After importing the new components, a check for redundancy is
      performed, and any components that are too similar are merged.
    """
    
    def __init__(self, dim, *points, kMax, 
                 # --- Hyperparameters ---
                 significance_level=0.05,
                 learning_rate=0.01,
                 max_idle_iterations=300,
                 fn_buffer_size=50,
                 fn_buffer_kMax=3,
                 nearby_mahal_threshold=None,
                 merge_dist_threshold=0.5):
        
        self.dim = dim
        self.kMax = kMax
        self.omega = learning_rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.fn_buffer_kMax = fn_buffer_kMax
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
        """Iteratively finds and merges the most similar pair of components."""
        while True: # Loop until no more merges are possible
            if self.n_components < 2: return
            
            min_dist, merge_pair = np.inf, None
            for i in range(self.n_components):
                for j in range(i + 1, self.n_components):
                    dist = self._bhattacharyya_distance(i, j)
                    if dist < min_dist:
                        min_dist, merge_pair = dist, (i, j)
            
            if min_dist < self.merge_dist_threshold:
                print(f"--- MERGING: Found components {merge_pair} with distance {min_dist:.2f}. Merging. ---")
                i, j = merge_pair
                pi_i, mu_i, C_i = self.weights[i], self.means[i], self.covariances[i]
                pi_j, mu_j, C_j = self.weights[j], self.means[j], self.covariances[j]
                
                pi_merged = pi_i + pi_j
                mu_merged = (pi_i * mu_i + pi_j * mu_j) / pi_merged
                C_merged = (pi_i * (C_i + np.outer(mu_i-mu_merged, mu_i-mu_merged)) +
                            pi_j * (C_j + np.outer(mu_j-mu_merged, mu_j-mu_merged))) / pi_merged
                
                indices_to_keep = [k for k in range(self.n_components) if k not in (i, j)]
                self.weights = np.append(self.weights[indices_to_keep], pi_merged)
                self.means = np.vstack((self.means[indices_to_keep], mu_merged))
                self.covariances = np.concatenate((self.covariances[indices_to_keep], [C_merged]), axis=0)
                self.idle_iterations = np.append(self.idle_iterations[indices_to_keep], 
                                                 min(self.idle_iterations[i], self.idle_iterations[j]))
            else:
                break # No more pairs are close enough, so exit the loop

    def update(self, point, feedback, prediction_result):
        was_predicted_inlier, j_star, all_dists = prediction_result
        if self.n_components > 0: self.idle_iterations += 1

        if was_predicted_inlier and feedback: # True Positive
            self.idle_iterations[all_dists < self.nearby_mahal_threshold] = 0
            mu_old = self.means[j_star]
            self.means[j_star] = (1-self.omega)*mu_old + self.omega*point
            residual = point - mu_old
            self.covariances[j_star] = (1-self.omega)*self.covariances[j_star] + self.omega*np.outer(residual, residual)
            self.weights[j_star] = (1-self.omega)*self.weights[j_star] + self.omega
            self.weights /= np.sum(self.weights)

        elif was_predicted_inlier and not feedback: # False Positive
            self._prune_idle_components()

        elif not was_predicted_inlier and feedback: # False Negative
            self.fn_buffer.append(point)
            print(f"False Negative detected. Buffer size: {len(self.fn_buffer)}/{self.fn_buffer_size}")
            
            if len(self.fn_buffer) >= self.fn_buffer_size:
                print(f"--- FN Buffer full. Training GMM and importing components. ---")
                buffer_data = np.array(self.fn_buffer)
                
                lowest_bic, best_gmm = np.infty, None
                for k in range(1, self.fn_buffer_kMax + 1):
                    if len(buffer_data) < k: break
                    gmm = GaussianMixture(n_components=k, covariance_type='full', random_state=0).fit(buffer_data)
                    bic = gmm.bic(buffer_data)
                    if bic < lowest_bic:
                        lowest_bic, best_gmm = bic, gmm
                
                if best_gmm is not None:
                    print(f"New GMM found {best_gmm.n_components_} new components to import.")
                    total_new_weight = self.omega * len(self.fn_buffer) / 100
                    self.weights *= (1 - total_new_weight)
                    
                    for i in range(best_gmm.n_components_):
                        new_weight = total_new_weight * best_gmm.weights_[i]
                        self.weights = np.append(self.weights, new_weight)
                        self.means = np.vstack([self.means, best_gmm.means_[i]])
                        self.covariances = np.concatenate([self.covariances, [best_gmm.covariances_[i]]], axis=0)
                        self.idle_iterations = np.append(self.idle_iterations, 0)
                
                self.fn_buffer = []

                # --- NEW STEP: Check for merges after importing new components ---
                print("--- Checking for redundancy after import... ---")
                self._merge_components()

if __name__ == '__main__':
    np.random.seed(0)
    data1 = np.random.randn(100, 2) + np.array([3, 3])
    data2 = np.random.randn(100, 2) + np.array([-3, -3])
    initial_data = np.vstack([data1, data2])

    # FIX: Pass dim positionally
    gmm = StreamingGMM(2, *initial_data, kMax=5, fn_buffer_size=40, fn_buffer_kMax=2, merge_dist_threshold=1.0)
    
    print(f"\nInitial model has {gmm.n_components} components.")
    print("\n--- Streaming new, partially overlapping bimodal cluster ---")
    new_cluster_1 = np.random.randn(25, 2) + np.array([4, 4])
    new_cluster_2 = np.random.randn(25, 2) + np.array([8, -8])
    new_points = np.vstack([new_cluster_1, new_cluster_2])
    np.random.shuffle(new_points)
    for i, point in enumerate(new_points):
        pred_res = gmm.predict(point)
        gmm.update(point, feedback=True, prediction_result=pred_res)
    print(f"\nFinal model has {gmm.n_components} components.")