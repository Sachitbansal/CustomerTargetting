# streaming_hybrid_advanced.py

import numpy as np
from sklearn.mixture import GaussianMixture
from scipy.stats import multivariate_normal, chi2
from scipy.linalg import inv, det

class StreamingHybridAdvanced:
    def __init__(self, num_dim, cat_dims, kMax, 
                 significance_level=0.05, learning_rate=0.02, neg_learning_rate=0.05,
                 max_idle_iterations=500, fn_buffer_size=50, fn_buffer_kMax=3,
                 merge_dist_threshold=0.6, weight_prune_threshold=0.005,
                 max_exemplars=6): # Stores up to 6 IDs
        
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

        self.weights = np.array([]); self.means = np.empty((0, self.num_dim))
        self.covariances = np.empty((0, self.num_dim, self.num_dim))
        self.idle_iterations = np.array([], dtype=int)
        
        # List of lists. self.exemplars[k] holds IDs for cluster k
        self.exemplars = [] 
        
        self.cat_probs = []
        self.fn_buffer_num = []; self.fn_buffer_cat = []
        self.fn_buffer_meta = [] # Buffer for IDs (for FN cases)

    @property
    def n_components(self): return len(self.weights)

    def fit_batch(self, X_num, X_cat, X_meta=None):
        """
        X_meta: List of items (e.g., customer_ids)
        """
        k_init = min(self.kMax, len(X_num))
        gmm = GaussianMixture(n_components=k_init, covariance_type='full', reg_covar=1e-5, random_state=42)
        labels = gmm.fit_predict(X_num)
        self.weights, self.means, self.covariances = gmm.weights_, gmm.means_, gmm.covariances_
        self.idle_iterations = np.zeros(self.n_components, dtype=int)
        self.cat_probs = []
        self.exemplars = [] 

        for k in range(self.n_components):
            # 1. Categorical Probs
            mask = (labels == k)
            sub_c = X_cat[mask] if np.sum(mask) > 0 else np.zeros((0, len(self.cat_dims)))
            cp = []
            for i, dim in enumerate(self.cat_dims):
                if len(sub_c) > 0:
                    cts = np.bincount(sub_c[:, i].astype(int), minlength=dim)
                    cp.append((cts + 0.5)/(np.sum(cts) + 0.5 * dim))
                else: cp.append(np.ones(dim)/dim)
            self.cat_probs.append(cp)

            # 2. Init Exemplars (Store IDs directly)
            k_indices = np.where(mask)[0]
            selected_indices = k_indices[:self.max_exemplars]
            cluster_exs = []
            if X_meta is not None:
                for idx in selected_indices:
                    cluster_exs.append(X_meta[idx])
            self.exemplars.append(cluster_exs)

    def predict_score(self, x_num, x_cat):
        if self.n_components == 0: return False, -1, -np.inf, np.inf, []
        best_s, best_k, best_m = -np.inf, -1, np.inf
        all_m = np.zeros(self.n_components)
        for k in range(self.n_components):
            try:
                cov = self.covariances[k] + np.eye(self.num_dim)*1e-5
                diff = x_num - self.means[k]
                m = diff.T @ inv(cov) @ diff
                all_m[k] = m
                lp_num = multivariate_normal.logpdf(x_num, mean=self.means[k], cov=cov)
            except: lp_num = -100; m = np.inf; all_m[k] = np.inf
            lp_cat = 0
            for i, v in enumerate(x_cat):
                v = int(v)
                p = self.cat_probs[k][i][v] if 0 <= v < self.cat_dims[i] else 1e-6
                lp_cat += np.log(p + 1e-9)
            if lp_num + lp_cat > best_s: best_s, best_k, best_m = lp_num + lp_cat, k, m
        
        is_in = (best_m < self.chi2_threshold) and (best_s > -100)
        
        # Return list of IDs
        current_exemplars = self.exemplars[best_k] if (best_k != -1 and best_k < len(self.exemplars)) else []
        
        return is_in, best_k, best_s, all_m, current_exemplars

    def update(self, x_num, x_cat, feedback, result, meta=None):
        is_in, k, _, all_m, _ = result 
        
        if self.n_components > 0: self.idle_iterations += 1
        
        if is_in and feedback: # TP
            self.idle_iterations[all_m < self.nearby_mahal_threshold] = 0
            self.means[k] = (1-self.omega)*self.means[k] + self.omega*x_num
            res = x_num - self.means[k]
            self.covariances[k] = (1-self.omega)*self.covariances[k] + self.omega*np.outer(res, res)
            for i, v in enumerate(x_cat):
                v = int(v)
                if 0 <= v < self.cat_dims[i]:
                    obs = np.zeros(self.cat_dims[i]); obs[v] = 1.0
                    self.cat_probs[k][i] = (1-self.omega)*self.cat_probs[k][i] + self.omega*obs
            self.weights[k] = (1-self.omega)*self.weights[k] + self.omega
            
            # --- LRU UPDATE FOR TP (Store ID) ---
            if meta is not None:
                self.exemplars[k].append(meta)
                if len(self.exemplars[k]) > self.max_exemplars:
                    self.exemplars[k].pop(0) 

            self._norm(); self._prune()

        elif is_in and not feedback: # FP
            self.weights[k] *= (1-self.delta)
            self._norm(); self._prune()

        elif not is_in and feedback: # FN
            self.fn_buffer_num.append(x_num)
            self.fn_buffer_cat.append(x_cat)
            self.fn_buffer_meta.append(meta) # Buffer ID
            if len(self.fn_buffer_num) >= self.fn_buffer_size: self._proc_buf()

    def _proc_buf(self):
        Xn, Xc = np.array(self.fn_buffer_num), np.array(self.fn_buffer_cat)
        Xm = self.fn_buffer_meta
        
        best_b, best_g = np.inf, None
        for k in range(1, self.fn_buffer_kMax+1):
            if len(Xn)<k: break
            g = GaussianMixture(n_components=k, reg_covar=1e-5, random_state=0).fit(Xn)
            if g.bic(Xn) < best_b: best_b, best_g = g.bic(Xn), g
            
        if best_g:
            lbs = best_g.predict(Xn)
            wt = self.omega * (len(Xn)/50.0)
            self.weights *= (1-wt)
            for i in range(best_g.n_components):
                self.weights = np.append(self.weights, wt*best_g.weights_[i])
                self.means = np.vstack([self.means, best_g.means_[i]])
                self.covariances = np.concatenate([self.covariances, [best_g.covariances_[i]]], axis=0)
                self.idle_iterations = np.append(self.idle_iterations, 0)
                
                sc = Xc[lbs==i]
                cp = []
                for fi, dim in enumerate(self.cat_dims):
                    if len(sc)>0:
                        c = np.bincount(sc[:, fi].astype(int), minlength=dim)
                        cp.append((c+0.1)/(np.sum(c)+0.1*dim))
                    else: cp.append(np.ones(dim)/dim)
                self.cat_probs.append(cp)

                # --- NEW CLUSTER EXEMPLARS (IDs) ---
                indices_in_new_cluster = np.where(lbs == i)[0]
                new_cluster_exs = []
                for idx in indices_in_new_cluster[:self.max_exemplars]:
                    if idx < len(Xm) and Xm[idx] is not None:
                        new_cluster_exs.append(Xm[idx])
                self.exemplars.append(new_cluster_exs)

        self.fn_buffer_num, self.fn_buffer_cat, self.fn_buffer_meta = [], [], []
        self._norm(); self._merge()

    def _prune(self):
        if self.n_components == 0: return
        kp = [(self.idle_iterations[i] < self.max_idle_iterations) or (self.weights[i] >= self.weight_prune_threshold) for i in range(self.n_components)]
        if not all(kp):
            idx = np.where(kp)[0]
            self.weights, self.means, self.covariances, self.idle_iterations = self.weights[idx], self.means[idx], self.covariances[idx], self.idle_iterations[idx]
            self.cat_probs = [self.cat_probs[i] for i in idx]
            self.exemplars = [self.exemplars[i] for i in idx]
            self._norm()

    def _merge(self):
        while self.n_components > 1:
            md, pr = np.inf, None
            for i in range(self.n_components):
                for j in range(i+1, self.n_components):
                    try:
                        C = (self.covariances[i]+self.covariances[j])/2 + np.eye(self.num_dim)*1e-6
                        d = 0.125*(self.means[i]-self.means[j]).T @ inv(C) @ (self.means[i]-self.means[j])
                        if d < md: md, pr = d, (i,j)
                    except: pass
            if md > self.merge_dist_threshold: break
            i, j = pr
            wn = self.weights[i]+self.weights[j]
            mn = (self.weights[i]*self.means[i]+self.weights[j]*self.means[j])/wn
            cn = (self.weights[i]*(self.covariances[i]+np.outer(self.means[i]-mn, self.means[i]-mn)) + self.weights[j]*(self.covariances[j]+np.outer(self.means[j]-mn, self.means[j]-mn)))/wn
            cpn = [(self.weights[i]*self.cat_probs[i][f]+self.weights[j]*self.cat_probs[j][f])/wn for f in range(len(self.cat_dims))]
            
            # --- MERGE LISTS ---
            merged_exs = self.exemplars[i] + self.exemplars[j]
            if len(merged_exs) > self.max_exemplars:
                merged_exs = merged_exs[-self.max_exemplars:]

            kp = [k for k in range(self.n_components) if k not in (i,j)]
            self.weights = np.append(self.weights[kp], wn)
            self.means = np.vstack((self.means[kp], mn))
            self.covariances = np.concatenate((self.covariances[kp], [cn]), axis=0)
            self.idle_iterations = np.append(self.idle_iterations[kp], 0)
            self.cat_probs = [self.cat_probs[k] for k in kp] + [cpn]
            
            self.exemplars = [self.exemplars[k] for k in kp] + [merged_exs]

    def _norm(self):
        if self.weights.sum() > 0: self.weights /= self.weights.sum()