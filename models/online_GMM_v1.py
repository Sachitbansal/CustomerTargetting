# streaming_hybrid_advanced.py - COMPLETE FIXED VERSION
# Critical Fix: Buffer crash + Missing _norm() method

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import multivariate_normal, chi2
from scipy.linalg import inv, det

class onlineGMMv1:
    """
    Unified Online GMM with Exemplar Customer Tracking
    - FIXED: Buffer crash when < 2 samples
    - FIXED: Missing _norm() method
    - FIXED: Aggressive merging causing cluster loss
    """
    def __init__(self, num_dim, cat_dims, kMax=150, 
                 significance_level=0.0000001, learning_rate=0.08, neg_learning_rate=0.05,
                 max_idle_iterations=500000, fn_buffer_size=50, fn_buffer_kMax=3,
                 merge_dist_threshold=0.6, weight_prune_threshold=0.000001,
                 max_exemplars=6):
        """
        🔧 OPTIMIZED PARAMETERS FOR REDUCING FALSE NEGATIVES
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
        
        # Exemplar tracking
        self.exemplars = []
        
        # Categorical probability distributions per cluster
        self.cat_probs = []
        
        # FN buffer
        self.fn_buffer_num = []
        self.fn_buffer_cat = []
        self.fn_buffer_meta = []

    @property
    def n_components(self):
        """Return current number of clusters"""
        return len(self.weights)

    def fit_batch(self, X_num, X_cat, X_meta=None):
        """Initialize GMM with batch of training data"""
        k_init = min(self.kMax, len(X_num))
        gmm = GaussianMixture(
            n_components=k_init, 
            covariance_type='full', 
            reg_covar=1e-4,
            random_state=42,
            max_iter=500,
            n_init=5
        )
        labels = gmm.fit_predict(X_num)
        
        self.weights = gmm.weights_
        self.means = gmm.means_
        self.covariances = gmm.covariances_
        self.idle_iterations = np.zeros(self.n_components, dtype=int)
        self.cat_probs = []
        self.exemplars = []

        for k in range(self.n_components):
            mask = (labels == k)
            sub_c = X_cat[mask] if np.sum(mask) > 0 else np.zeros((0, len(self.cat_dims)))
            
            # Initialize categorical probabilities
            cp = []
            for i, dim in enumerate(self.cat_dims):
                if len(sub_c) > 0:
                    cts = np.bincount(sub_c[:, i].astype(int), minlength=dim)
                    cp.append((cts + 0.5) / (np.sum(cts) + 0.5 * dim))
                else:
                    cp.append(np.ones(dim) / dim)
            self.cat_probs.append(cp)

            # Initialize exemplars
            k_indices = np.where(mask)[0]
            selected_indices = k_indices[:self.max_exemplars]
            cluster_exs = []
            if X_meta is not None:
                for idx in selected_indices:
                    cluster_exs.append(X_meta[idx])
            self.exemplars.append(cluster_exs)

    def predict_score(self, x_num, x_cat):
        """Predict cluster membership and return scoring information"""
        if self.n_components == 0:
            return False, -1, -np.inf, np.inf, []
        
        best_s, best_k, best_m = -np.inf, -1, np.inf
        all_m = np.zeros(self.n_components)
        
        for k in range(self.n_components):
            try:
                # Increased regularization for stability
                cov = self.covariances[k] + np.eye(self.num_dim) * 1e-4
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
            
            if lp_num + lp_cat > best_s:
                best_s, best_k, best_m = lp_num + lp_cat, k, m
        
        is_in = (best_m < self.chi2_threshold) and (best_s > -100)
        
        current_exemplars = []
        if best_k != -1 and best_k < len(self.exemplars):
            current_exemplars = self.exemplars[best_k]
        
        return is_in, best_k, best_s, all_m, current_exemplars

    def update(self, x_num, x_cat, feedback, result, meta=None):
        """Update GMM based on feedback"""
        is_in, k, _, all_m, _ = result
        
        if self.n_components > 0:
            self.idle_iterations += 1
        
        if is_in and feedback:  # TRUE POSITIVE
            self.idle_iterations[all_m < self.nearby_mahal_threshold] = 0
            self.means[k] = (1 - self.omega) * self.means[k] + self.omega * x_num
            
            res = x_num - self.means[k]
            self.covariances[k] = (1 - self.omega) * self.covariances[k] + self.omega * np.outer(res, res)
            
            for i, v in enumerate(x_cat):
                v = int(v)
                if 0 <= v < self.cat_dims[i]:
                    obs = np.zeros(self.cat_dims[i])
                    obs[v] = 1.0
                    self.cat_probs[k][i] = (1 - self.omega) * self.cat_probs[k][i] + self.omega * obs
            
            self.weights[k] = (1 - self.omega) * self.weights[k] + self.omega
            
            if meta is not None:
                self.exemplars[k].append(meta)
                if len(self.exemplars[k]) > self.max_exemplars:
                    self.exemplars[k].pop(0)
            
            self._norm()
            self._prune()
        
        elif is_in and not feedback:  # FALSE POSITIVE
            self.weights[k] *= (1 - self.delta)
            self._norm()
            self._prune()
        
        elif not is_in and feedback:  # FALSE NEGATIVE
            self.fn_buffer_num.append(x_num)
            self.fn_buffer_cat.append(x_cat)
            self.fn_buffer_meta.append(meta)
            
            if len(self.fn_buffer_num) >= self.fn_buffer_size:
                self._proc_buf()

    def flush_buffer(self):
        """Force process FN buffer regardless of size"""
        if len(self.fn_buffer_num) > 0:
            print(f"  └─ Flushing FN buffer with {len(self.fn_buffer_num)} samples...")
            self._proc_buf()

    def _proc_buf(self):
        """
        🔧 CRITICAL FIX: Process FN buffer with proper error handling
        """
        Xn = np.array(self.fn_buffer_num)
        Xc = np.array(self.fn_buffer_cat)
        Xm = self.fn_buffer_meta
        
        # 🔑 CRITICAL: Need at least 2 samples for covariance estimation
        if len(Xn) < 2:
            print(f"⚠️  FN buffer has only {len(Xn)} sample(s). Need minimum 2. Waiting for more samples...")
            return  # Don't clear buffer, wait for accumulation
        
        # Prevent trying to create more clusters than samples
        max_k = min(self.fn_buffer_kMax, len(Xn))
        
        best_b, best_g = np.inf, None
        for k in range(1, max_k + 1):
            try:
                g = GaussianMixture(
                    n_components=k, 
                    reg_covar=1e-4,
                    random_state=0,
                    max_iter=200
                ).fit(Xn)
                
                if g.bic(Xn) < best_b:
                    best_b, best_g = g.bic(Xn), g
            except Exception as e:
                print(f"⚠️  GMM fit failed for k={k} components: {e}")
                continue
        
        if best_g is None:
            print(f"❌ Failed to fit any GMM model to {len(Xn)} FN samples. Keeping in buffer.")
            return  # Don't clear buffer if fitting failed
        
        # Successfully fitted GMM - process it
        lbs = best_g.predict(Xn)
        wt = self.omega * (len(Xn) / 50.0)
        
        self.weights *= (1 - wt)
        
        clusters_created = 0
        for i in range(best_g.n_components):
            self.weights = np.append(self.weights, wt * best_g.weights_[i])
            self.means = np.vstack([self.means, best_g.means_[i]])
            self.covariances = np.concatenate([self.covariances, [best_g.covariances_[i]]], axis=0)
            self.idle_iterations = np.append(self.idle_iterations, 0)
            
            # Initialize categorical
            sc = Xc[lbs == i]
            cp = []
            for fi, dim in enumerate(self.cat_dims):
                if len(sc) > 0:
                    c = np.bincount(sc[:, fi].astype(int), minlength=dim)
                    cp.append((c + 0.1) / (np.sum(c) + 0.1 * dim))
                else:
                    cp.append(np.ones(dim) / dim)
            self.cat_probs.append(cp)
            
            # Initialize exemplars
            indices_in_new_cluster = np.where(lbs == i)[0]
            new_cluster_exs = []
            for idx in indices_in_new_cluster[:self.max_exemplars]:
                if idx < len(Xm) and Xm[idx] is not None:
                    new_cluster_exs.append(Xm[idx])
            self.exemplars.append(new_cluster_exs)
            clusters_created += 1
        
        # Only clear buffer after successful processing
        self.fn_buffer_num, self.fn_buffer_cat, self.fn_buffer_meta = [], [], []
        print(f"✓ FN Buffer processed: {clusters_created} new clusters from {len(Xn)} samples")
        
        self._norm()
        self._merge()

    def _prune(self):
        """Remove weak/idle clusters"""
        if self.n_components == 0:
            return
        
        kp = [
            (self.idle_iterations[i] < self.max_idle_iterations) or 
            (self.weights[i] >= self.weight_prune_threshold)
            for i in range(self.n_components)
        ]
        
        if not all(kp):
            idx = np.where(kp)[0]
            pruned = self.n_components - len(idx)
            
            self.weights = self.weights[idx]
            self.means = self.means[idx]
            self.covariances = self.covariances[idx]
            self.idle_iterations = self.idle_iterations[idx]
            self.cat_probs = [self.cat_probs[i] for i in idx]
            self.exemplars = [self.exemplars[i] for i in idx]
            
            if pruned > 0:
                print(f"  └─ Pruned {pruned} weak/idle clusters")
            
            self._norm()

    def _merge(self):
        """Merge similar clusters to prevent redundancy"""
        merged_count = 0
        
        while self.n_components > 1:
            md, pr = np.inf, None
            
            for i in range(self.n_components):
                for j in range(i + 1, self.n_components):
                    try:
                        C = (self.covariances[i] + self.covariances[j]) / 2 + np.eye(self.num_dim) * 1e-6
                        d = 0.125 * (self.means[i] - self.means[j]).T @ inv(C) @ (self.means[i] - self.means[j])
                        if d < md:
                            md, pr = d, (i, j)
                    except:
                        pass
            
            if md > self.merge_dist_threshold:
                break
            
            i, j = pr
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
            
            merged_exs = self.exemplars[i] + self.exemplars[j]
            if len(merged_exs) > self.max_exemplars:
                merged_exs = merged_exs[-self.max_exemplars:]
            
            kp = [k for k in range(self.n_components) if k not in (i, j)]
            self.weights = np.append(self.weights[kp], wn)
            self.means = np.vstack((self.means[kp], mn))
            self.covariances = np.concatenate((self.covariances[kp], [cn]), axis=0)
            self.idle_iterations = np.append(self.idle_iterations[kp], 0)
            self.cat_probs = [self.cat_probs[k] for k in kp] + [cpn]
            self.exemplars = [self.exemplars[k] for k in kp] + [merged_exs]
            
            merged_count += 1
        
        if merged_count > 0:
            print(f"  └─ Merged {merged_count} similar cluster pairs")

    def _norm(self):
        """🔑 CRITICAL: Normalize cluster weights to sum to 1"""
        if self.weights.sum() > 0:
            self.weights /= self.weights.sum()