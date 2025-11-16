'''
This class represents the most complex and adaptive strategy. It combines the active punishment of Class 5
with the powerful novelty handling of Class 2/4. When False Positives occur, the responsible component is
penalized. When a new concept is detected, the model buffers the novel points, trains a full GMM on them,
imports all the new components, and then runs a merging pass to ensure they are integrated efficiently.
This model is designed for maximum flexibility and continuous self-optimization in complex, evolving
data environments.
'''

# File: gmm_class_6.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2
from scipy.linalg import inv, det

class StreamingGMM:
    """
    Implements a streaming GMM with active punishment and full GMM novelty handling.
    
    - Aging & Weight Pruning: Components are pruned if idle or if their weight is too low.
    - True Positives: The winning component is updated, nearby components' idle counters
      are reset, and pruning checks are performed.
    - False Positives: The responsible component is 'punished' via weight reduction.
      Pruning checks are performed.
    - False Negatives: Novel points are buffered. When full, a new GMM is trained on them,
      and all its resulting components are imported.
    - Merging: After importing new components, a redundancy check is performed, and
      similar components are merged.
    """
    
    def __init__(self, dim, *points, kMax, 
                 # --- Hyperparameters ---
                 significance_level=0.05,
                 learning_rate=0.01,
                 neg_learning_rate=0.05,
                 max_idle_iterations=300,
                 fn_buffer_size=50,
                 fn_buffer_kMax=3,
                 nearby_mahal_threshold=None,
                 merge_dist_threshold=0.5,
                 weight_prune_threshold=0.005):
        
        self.dim = dim
        self.kMax = kMax
        self.omega = learning_rate
        self.delta = neg_learning_rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.fn_buffer_kMax = fn_buffer_kMax
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
        if self.n_components == 0: return
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
            print(f"--- PRUNING: Removed {pruned_count} components. ---")

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
        while True:
            if self.n_components < 2: return
            min_dist, merge_pair = np.inf, None
            for i in range(self.n_components):
                for j in range(i + 1, self.n_components):
                    dist = self._bhattacharyya_distance(i, j)
                    if dist < min_dist: min_dist, merge_pair = dist, (i, j)
            
            if min_dist < self.merge_dist_threshold:
                print(f"--- MERGING: Found components {merge_pair}. Merging. ---")
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
            else: break

    def update(self, point, feedback, prediction_result):
        was_predicted_inlier, j_star, all_dists = prediction_result
        if self.n_components > 0: self.idle_iterations += 1

        if was_predicted_inlier and feedback: # True Positive
            self.idle_iterations[all_dists < self.nearby_mahal_threshold] = 0
            self._prune_components()
            if j_star >= self.n_components: return
            mu_old = self.means[j_star]
            self.means[j_star] = (1-self.omega)*mu_old + self.omega*point
            residual = point - mu_old
            self.covariances[j_star] = (1-self.omega)*self.covariances[j_star] + self.omega*np.outer(residual, residual)
            self.weights[j_star] = (1-self.omega)*self.weights[j_star] + self.omega
            self.weights /= np.sum(self.weights)

        elif was_predicted_inlier and not feedback: # False Positive
            print(f"--- PUNISHMENT: Reducing weight of component {j_star} for False Positive. ---")
            self.weights[j_star] *= (1 - self.delta)
            self.weights /= np.sum(self.weights)
            self._prune_components()

        elif not was_predicted_inlier and feedback: # False Negative
            self.fn_buffer.append(point)
            if len(self.fn_buffer) >= self.fn_buffer_size:
                print(f"--- FN Buffer full. Training GMM and importing components. ---")
                buffer_data = np.array(self.fn_buffer)
                lowest_bic, best_gmm = np.infty, None
                for k in range(1, self.fn_buffer_kMax + 1):
                    if len(buffer_data) < k: break
                    gmm = GaussianMixture(n_components=k, covariance_type='full', random_state=0).fit(buffer_data)
                    bic = gmm.bic(buffer_data)
                    if bic < lowest_bic: lowest_bic, best_gmm = bic, gmm
                if best_gmm is not None:
                    print(f"New GMM found {best_gmm.n_components} new components to import.")
                    total_new_weight = self.omega * len(self.fn_buffer) / 100
                    self.weights *= (1 - total_new_weight)
                    for i in range(best_gmm.n_components):
                        new_weight = total_new_weight * best_gmm.weights_[i]
                        self.weights = np.append(self.weights, new_weight)
                        self.means = np.vstack([self.means, best_gmm.means_[i]])
                        self.covariances = np.concatenate([self.covariances, [best_gmm.covariances_[i]]], axis=0)
                        self.idle_iterations = np.append(self.idle_iterations, 0)
                self.fn_buffer = []
                print("--- Checking for redundancy after import... ---")
                self._merge_components()

if __name__ == '__main__':
    np.random.seed(0)
    data1 = np.random.randn(100, 2) + np.array([3, 3])
    data2 = np.random.randn(100, 2) + np.array([-3, -3])
    initial_data = np.vstack([data1, data2])

    # --- FIX: Call constructor with dim as a positional argument ---
    gmm = StreamingGMM(2, *initial_data, kMax=5, fn_buffer_size=40, 
                             fn_buffer_kMax=2, merge_dist_threshold=1.0,
                             neg_learning_rate=0.1, weight_prune_threshold=0.01)
                             
    print(f"\nInitial model has {gmm.n_components} components.")
    
    # Simulate both outliers (for punishment) and a new cluster (for novelty)
    print("\n--- Streaming outliers (False Positives) and a new bimodal cluster (False Negatives) ---")
    outliers = (np.random.rand(10, 2) * 10 - 5)
    new_cluster_1 = np.random.randn(25, 2) + np.array([5, -5])
    new_cluster_2 = np.random.randn(25, 2) + np.array([8, -8])
    
    # Interleave the points
    stream_points = np.vstack([outliers, new_cluster_1, new_cluster_2])
    stream_labels = [False] * 10 + [True] * 50
    
    combined = list(zip(stream_points, stream_labels))
    np.random.shuffle(combined)
    stream_points, stream_labels = zip(*combined)

    for point, label in zip(stream_points, stream_labels):
        pred_res = gmm.predict(point)
        gmm.update(point, feedback=label, prediction_result=pred_res)
    
    print(f"\nFinal model has {gmm.n_components} components.")