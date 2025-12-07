# streaming_hybrid_advanced.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import multivariate_normal, chi2
from scipy.linalg import inv, det

class onlineGMMv1:
    """
    Unified Online GMM with Exemplar Customer Tracking
    - Core algorithm from StreamingHybridAdvanced
    - Interface and exemplar functionality for production use
    """
    def __init__(self, num_dim, cat_dims, kMax, 
                 significance_level=0.05, learning_rate=0.02, neg_learning_rate=0.05,
                 max_idle_iterations=500, fn_buffer_size=50, fn_buffer_kMax=3,
                 merge_dist_threshold=0.6, weight_prune_threshold=0.005,
                 max_exemplars=6):
        """
        Initialize Online GMM with exemplar tracking
        
        Args:
            num_dim: Number of numerical dimensions
            cat_dims: List of categorical dimension cardinalities
            kMax: Maximum number of clusters
            significance_level: Chi-squared test significance level (default 0.05)
            learning_rate: Learning rate for positive feedback (TP) (default 0.02)
            neg_learning_rate: Learning rate for negative feedback (FP) (default 0.05)
            max_idle_iterations: Prune clusters idle for this many iterations (default 500)
            fn_buffer_size: Buffer size for FN samples before processing (default 50)
            fn_buffer_kMax: Max clusters to create from FN buffer (default 3)
            merge_dist_threshold: Mahalanobis distance threshold for merging (default 0.6)
            weight_prune_threshold: Minimum weight to keep cluster (default 0.005)
            max_exemplars: Maximum exemplar customer IDs per cluster (default 6)
        """
        
        self.num_dim = num_dim
        self.cat_dims = cat_dims
        self.kMax = kMax
        self.omega = learning_rate
        self.delta = neg_learning_rate
        self.max_idle_iterations = max_idle_iterations
        self.fn_buffer_size = fn_buffer_size
        self.fn_buffer_kMax = fn_buffer_kMax
        self.merge_dist_threshold = merge_dist_threshold
        self.weight_prune_threshold = weight_prune_threshold
        self.chi2_threshold = chi2.ppf(1 - significance_level, df=self.num_dim)
        self.nearby_mahal_threshold = self.chi2_threshold * 1.5
        self.max_exemplars = max_exemplars

        # Cluster parameters
        self.weights = np.array([])
        self.means = np.empty((0, self.num_dim))
        self.covariances = np.empty((0, self.num_dim, self.num_dim))
        self.idle_iterations = np.array([], dtype=int)
        
        # Exemplar tracking: List of lists where exemplars[k] holds customer IDs for cluster k
        self.exemplars = []
        
        # Categorical probability distributions per cluster
        self.cat_probs = []
        
        # FN buffer: stores samples that were rejected but should have been accepted
        self.fn_buffer_num = []   # Numerical features
        self.fn_buffer_cat = []   # Categorical features
        self.fn_buffer_meta = []  # Customer IDs (metadata)

    @property
    def n_components(self):
        """Return current number of clusters"""
        return len(self.weights)

    def fit_batch(self, X_num, X_cat, X_meta=None):
        """
        Initialize GMM with batch of training data
        
        Args:
            X_num: Numerical features array (n_samples, num_dim)
            X_cat: Categorical features array (n_samples, n_cat_features)
            X_meta: List of customer IDs or metadata (optional)
        """
        k_init = min(self.kMax, len(X_num))
        gmm = GaussianMixture(n_components=k_init, covariance_type='full', 
                             reg_covar=1e-5, random_state=42)
        labels = gmm.fit_predict(X_num)
        
        # Initialize cluster parameters
        self.weights = gmm.weights_
        self.means = gmm.means_
        self.covariances = gmm.covariances_
        self.idle_iterations = np.zeros(self.n_components, dtype=int)
        self.cat_probs = []
        self.exemplars = []

        for k in range(self.n_components):
            mask = (labels == k)
            
            # 1. Initialize categorical probabilities for this cluster
            sub_c = X_cat[mask] if np.sum(mask) > 0 else np.zeros((0, len(self.cat_dims)))
            cp = []
            for i, dim in enumerate(self.cat_dims):
                if len(sub_c) > 0:
                    cts = np.bincount(sub_c[:, i].astype(int), minlength=dim)
                    cp.append((cts + 0.5) / (np.sum(cts) + 0.5 * dim))
                else:
                    cp.append(np.ones(dim) / dim)
            self.cat_probs.append(cp)

            # 2. Initialize exemplar customer IDs for this cluster
            k_indices = np.where(mask)[0]
            selected_indices = k_indices[:self.max_exemplars]
            cluster_exs = []
            if X_meta is not None:
                for idx in selected_indices:
                    cluster_exs.append(X_meta[idx])
            self.exemplars.append(cluster_exs)

    def predict_score(self, x_num, x_cat):
        """
        Predict cluster membership and return scoring information
        
        Args:
            x_num: Numerical features for single sample
            x_cat: Categorical features for single sample
            
        Returns:
            Tuple: (is_in, best_k, best_score, all_mahalanobis, exemplar_ids)
                - is_in: Boolean, whether sample belongs to any cluster
                - best_k: Best matching cluster index (-1 if none)
                - best_score: Log probability score of best cluster
                - all_mahalanobis: Array of Mahalanobis distances to all clusters
                - exemplar_ids: List of exemplar customer IDs from best cluster
        """
        if self.n_components == 0:
            return False, -1, -np.inf, np.inf, []
        
        best_s, best_k, best_m = -np.inf, -1, np.inf
        all_m = np.zeros(self.n_components)
        
        for k in range(self.n_components):
            try:
                cov = self.covariances[k] + np.eye(self.num_dim) * 1e-5
                diff = x_num - self.means[k]
                m = diff.T @ inv(cov) @ diff
                all_m[k] = m
                lp_num = multivariate_normal.logpdf(x_num, mean=self.means[k], cov=cov)
            except:
                lp_num = -100
                m = np.inf
                all_m[k] = np.inf
            
            # Calculate categorical log probability
            lp_cat = 0
            for i, v in enumerate(x_cat):
                v = int(v)
                p = self.cat_probs[k][i][v] if 0 <= v < self.cat_dims[i] else 1e-6
                lp_cat += np.log(p + 1e-9)
            
            # Update best cluster if this one has higher score
            if lp_num + lp_cat > best_s:
                best_s, best_k, best_m = lp_num + lp_cat, k, m
        
        # Determine if sample belongs to best cluster (using chi-squared test)
        is_in = (best_m < self.chi2_threshold) and (best_s > -100)
        
        # Get exemplar customer IDs from best cluster
        current_exemplars = []
        if best_k != -1 and best_k < len(self.exemplars):
            current_exemplars = self.exemplars[best_k]
        
        return is_in, best_k, best_s, all_m, current_exemplars

    def update(self, x_num, x_cat, feedback, result, meta=None):
        """
        Update GMM based on feedback
        
        Args:
            x_num: Numerical features for single sample
            x_cat: Categorical features for single sample
            feedback: Boolean, ground truth label (True = positive, False = negative)
            result: Output from predict_score() for this sample
            meta: Customer ID or metadata to store as exemplar (optional)
        
        Feedback types:
            - TP (True Positive): is_in=True, feedback=True → Reinforce cluster
            - FP (False Positive): is_in=True, feedback=False → Penalize cluster
            - FN (False Negative): is_in=False, feedback=True → Buffer for new cluster
            - TN (True Negative): is_in=False, feedback=False → No action
        """
        is_in, k, _, all_m, _ = result
        
        # Increment idle counter for all clusters
        if self.n_components > 0:
            self.idle_iterations += 1
        
        if is_in and feedback:  # TRUE POSITIVE: Reinforce cluster
            # Reset idle counter for nearby clusters
            self.idle_iterations[all_m < self.nearby_mahal_threshold] = 0
            
            # Update cluster mean
            self.means[k] = (1 - self.omega) * self.means[k] + self.omega * x_num
            
            # Update cluster covariance
            res = x_num - self.means[k]
            self.covariances[k] = (1 - self.omega) * self.covariances[k] + self.omega * np.outer(res, res)
            
            # Update categorical probabilities
            for i, v in enumerate(x_cat):
                v = int(v)
                if 0 <= v < self.cat_dims[i]:
                    obs = np.zeros(self.cat_dims[i])
                    obs[v] = 1.0
                    self.cat_probs[k][i] = (1 - self.omega) * self.cat_probs[k][i] + self.omega * obs
            
            # Increase cluster weight
            self.weights[k] = (1 - self.omega) * self.weights[k] + self.omega
            
            # Update exemplars with LRU policy: append new ID, remove oldest if exceeds max
            if meta is not None:
                self.exemplars[k].append(meta)
                if len(self.exemplars[k]) > self.max_exemplars:
                    self.exemplars[k].pop(0)  # Remove oldest exemplar
            
            self._norm()
            self._prune()
        
        elif is_in and not feedback:  # FALSE POSITIVE: Penalize cluster
            # Reduce cluster weight
            self.weights[k] *= (1 - self.delta)
            
            self._norm()
            self._prune()
        
        elif not is_in and feedback:  # FALSE NEGATIVE: Buffer for new cluster creation
            self.fn_buffer_num.append(x_num)
            self.fn_buffer_cat.append(x_cat)
            self.fn_buffer_meta.append(meta)
            
            # Process buffer when full
            if len(self.fn_buffer_num) >= self.fn_buffer_size:
                self._proc_buf()
        
        # TRUE NEGATIVE (not is_in and not feedback): No action needed

    def _proc_buf(self):
        """
        Process FN buffer: Create new clusters from misclassified positive samples
        Uses BIC to determine optimal number of new clusters
        """
        Xn = np.array(self.fn_buffer_num)
        Xc = np.array(self.fn_buffer_cat)
        Xm = self.fn_buffer_meta
        
        # Find best number of clusters using BIC
        best_b, best_g = np.inf, None
        for k in range(1, self.fn_buffer_kMax + 1):
            if len(Xn) < k:
                break
            g = GaussianMixture(n_components=k, reg_covar=1e-5, random_state=0).fit(Xn)
            if g.bic(Xn) < best_b:
                best_b, best_g = g.bic(Xn), g
        
        if best_g:
            lbs = best_g.predict(Xn)
            wt = self.omega * (len(Xn) / 50.0)
            
            # Reduce weight of existing clusters to make room for new ones
            self.weights *= (1 - wt)
            
            # Add new clusters from buffer
            for i in range(best_g.n_components):
                self.weights = np.append(self.weights, wt * best_g.weights_[i])
                self.means = np.vstack([self.means, best_g.means_[i]])
                self.covariances = np.concatenate([self.covariances, [best_g.covariances_[i]]], axis=0)
                self.idle_iterations = np.append(self.idle_iterations, 0)
                
                # Initialize categorical probabilities for new cluster
                sc = Xc[lbs == i]
                cp = []
                for fi, dim in enumerate(self.cat_dims):
                    if len(sc) > 0:
                        c = np.bincount(sc[:, fi].astype(int), minlength=dim)
                        cp.append((c + 0.1) / (np.sum(c) + 0.1 * dim))
                    else:
                        cp.append(np.ones(dim) / dim)
                self.cat_probs.append(cp)
                
                # Initialize exemplars for new cluster
                indices_in_new_cluster = np.where(lbs == i)[0]
                new_cluster_exs = []
                for idx in indices_in_new_cluster[:self.max_exemplars]:
                    if idx < len(Xm) and Xm[idx] is not None:
                        new_cluster_exs.append(Xm[idx])
                self.exemplars.append(new_cluster_exs)
        
        # Clear buffer
        self.fn_buffer_num, self.fn_buffer_cat, self.fn_buffer_meta = [], [], []
        self._norm()
        self._merge()

    def _prune(self):
        """
        Remove clusters that are:
        1. Idle for too long (no updates for max_idle_iterations), OR
        2. Have very low weight (< weight_prune_threshold)
        """
        if self.n_components == 0:
            return
        
        # Determine which clusters to keep
        kp = [
            (self.idle_iterations[i] < self.max_idle_iterations) or 
            (self.weights[i] >= self.weight_prune_threshold)
            for i in range(self.n_components)
        ]
        
        if not all(kp):
            idx = np.where(kp)[0]
            self.weights = self.weights[idx]
            self.means = self.means[idx]
            self.covariances = self.covariances[idx]
            self.idle_iterations = self.idle_iterations[idx]
            self.cat_probs = [self.cat_probs[i] for i in idx]
            self.exemplars = [self.exemplars[i] for i in idx]
            self._norm()

    def _merge(self):
        """
        Merge similar clusters to prevent over-fitting
        Uses Mahalanobis distance to measure cluster similarity
        """
        while self.n_components > 1:
            md, pr = np.inf, None
            
            # Find closest pair of clusters
            for i in range(self.n_components):
                for j in range(i + 1, self.n_components):
                    try:
                        C = (self.covariances[i] + self.covariances[j]) / 2 + np.eye(self.num_dim) * 1e-6
                        d = 0.125 * (self.means[i] - self.means[j]).T @ inv(C) @ (self.means[i] - self.means[j])
                        if d < md:
                            md, pr = d, (i, j)
                    except:
                        pass
            
            # Stop if no clusters are close enough to merge
            if md > self.merge_dist_threshold:
                break
            
            i, j = pr
            
            # Merge clusters i and j
            wn = self.weights[i] + self.weights[j]
            mn = (self.weights[i] * self.means[i] + self.weights[j] * self.means[j]) / wn
            cn = (
                self.weights[i] * (self.covariances[i] + np.outer(self.means[i] - mn, self.means[i] - mn)) +
                self.weights[j] * (self.covariances[j] + np.outer(self.means[j] - mn, self.means[j] - mn))
            ) / wn
            cpn = [
                (self.weights[i] * self.cat_probs[i][f] + self.weights[j] * self.cat_probs[j][f]) / wn
                for f in range(len(self.cat_dims))
            ]
            
            # Merge exemplar lists (keep most recent up to max_exemplars)
            merged_exs = self.exemplars[i] + self.exemplars[j]
            if len(merged_exs) > self.max_exemplars:
                merged_exs = merged_exs[-self.max_exemplars:]  # Keep most recent
            
            # Remove old clusters and add merged cluster
            kp = [k for k in range(self.n_components) if k not in (i, j)]
            self.weights = np.append(self.weights[kp], wn)
            self.means = np.vstack((self.means[kp], mn))
            self.covariances = np.concatenate((self.covariances[kp], [cn]), axis=0)
            self.idle_iterations = np.append(self.idle_iterations[kp], 0)
            self.cat_probs = [self.cat_probs[k] for k in kp] + [cpn]
            self.exemplars = [self.exemplars[k] for k in kp] + [merged_exs]

    def _norm(self):
        """Normalize cluster weights to sum to 1"""
        if self.weights.sum() > 0:
            self.weights /= self.weights.sum()