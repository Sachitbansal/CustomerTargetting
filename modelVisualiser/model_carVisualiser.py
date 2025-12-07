"""
Real-time GMM Model Visualization System
Monitors model_car.json and generates visualization images every 15 seconds
HANDLES DYNAMIC CLUSTER COUNT CHANGES
"""
import sys
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
import time
import os
from datetime import datetime
from sklearn.decomposition import PCA
import hashlib

# Configuration
MODEL_PATH = Path(__file__).parent.parent / "Persistence/model_car.json"
OUTPUT_DIR = Path(__file__).parent.parent / "modelVisualiser"
GIF_IMAGES_DIR = os.path.join(OUTPUT_DIR, "gif_images")
CLUSTER_STATS_DIR = os.path.join(OUTPUT_DIR, "cluster_stats")
WEIGHT_EVOLUTION_DIR = os.path.join(OUTPUT_DIR, "weight_evolution")
CLUSTER_COUNT_DIR = os.path.join(OUTPUT_DIR, "cluster_count_evolution")
REFRESH_INTERVAL = 5  # seconds

os.makedirs(GIF_IMAGES_DIR, exist_ok=True)
os.makedirs(CLUSTER_STATS_DIR, exist_ok=True)
os.makedirs(WEIGHT_EVOLUTION_DIR, exist_ok=True)
os.makedirs(CLUSTER_COUNT_DIR, exist_ok=True)

# Global state for tracking evolution
weight_history = []  # List of weight arrays (can have different lengths)
cluster_count_history = []  # Track number of clusters over time
timestamp_history = []
last_file_hash = None


def compute_file_hash(filepath):
    """Compute MD5 hash of file to detect changes"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def load_model_data(filepath):
    """Load and parse the model JSON file"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"⚠️  Model file not found: {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"⚠️  Error parsing JSON from: {filepath}")
        return None


def create_pca_projection(means, scaler_data):
    """Create PCA projection for visualization"""
    # Reconstruct scaled means (they're already standardized in the JSON)
    means_array = np.array(means)
    
    # Fit PCA on the means
    pca = PCA(n_components=2, random_state=42)
    means_2d = pca.fit_transform(means_array)
    
    return pca, means_2d


def plot_gmm_clusters(data, output_path):
    """
    Generate the main GMM cluster visualization (like the GIF frames)
    Handles dynamic number of clusters
    Shows each Gaussian component as a separate ellipse
    """
    gmm_data = data['gmm']
    scaler_data = data['scaler']
    
    weights = np.array(gmm_data['weights'])
    means = np.array(gmm_data['means'])
    covariances = np.array(gmm_data['covariances'])
    
    n_clusters = len(weights)
    
    # Create PCA projection
    pca, means_2d = create_pca_projection(means, scaler_data)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 9))
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#1a1a1a')
    
    # Plot each cluster as a SEPARATE ellipse (one per Gaussian component)
    for idx, (mean_orig, cov, weight) in enumerate(zip(means, covariances, weights)):
        if weight < 0.001:  # Skip negligible clusters
            continue
        
        # Project mean to 2D
        mean_2d = pca.transform(mean_orig.reshape(1, -1))[0]
        
        # Project covariance to 2D space
        cov_2d = pca.components_ @ cov @ pca.components_.T
        
        try:
            # Eigenvalue decomposition for ellipse parameters
            eigenvalues, eigenvectors = np.linalg.eigh(cov_2d)
            angle = np.degrees(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0]))
            
            # Scale by chi-square quantile (95% confidence interval)
            width, height = 2 * np.sqrt(np.abs(eigenvalues) * 5.991)
            
            # Color intensity based on weight (more weight = more visible)
            alpha = min(0.2 + weight * 3, 0.6)
            
            # Use green color scheme like original
            # Draw ellipse for this Gaussian component
            ellipse = Ellipse(
                mean_2d, width, height, angle=angle,
                facecolor='green', alpha=alpha,
                edgecolor='darkgreen', linewidth=2
            )
            ax.add_patch(ellipse)
            
            # Add cluster label with weight
            ax.text(
                mean_2d[0], mean_2d[1], f'{idx}',
                fontsize=9, ha='center', va='center',
                color='white', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.6)
            )
            
            # Add weight as a small annotation
            ax.text(
                mean_2d[0], mean_2d[1] - 0.3, f'{weight:.1%}',
                fontsize=7, ha='center', va='top',
                color='lightgreen', fontweight='bold'
            )
            
        except np.linalg.LinAlgError:
            # Skip if covariance is singular
            print(f"  ⚠️  Cluster {idx}: Singular covariance, skipping visualization")
            continue
    
    # Calculate appropriate axis limits to show all ellipses
    if len(means_2d) > 0:
        all_x = means_2d[:, 0]
        all_y = means_2d[:, 1]
        
        # Get bounds with padding
        x_range = all_x.max() - all_x.min()
        y_range = all_y.max() - all_y.min()
        padding = max(x_range, y_range) * 0.3  # 30% padding
        
        ax.set_xlim(all_x.min() - padding, all_x.max() + padding)
        ax.set_ylim(all_y.min() - padding, all_y.max() + padding)
    
    # Make axes equal aspect ratio so ellipses aren't distorted
    ax.set_aspect('equal', adjustable='box')
    
    # Styling
    ax.set_xlabel('PCA Component 1', fontsize=12, color='white', fontweight='bold')
    ax.set_ylabel('PCA Component 2', fontsize=12, color='white', fontweight='bold')
    ax.set_title(
        f'Car Loan Approval - GMM Clusters (Positive Class)\n'
        f'{n_clusters} Active Components | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        fontsize=14, color='white', fontweight='bold', pad=20
    )
    
    ax.tick_params(colors='white', labelsize=10)
    ax.spines['bottom'].set_color('#333333')
    ax.spines['top'].set_color('#333333')
    ax.spines['left'].set_color('#333333')
    ax.spines['right'].set_color('#333333')
    ax.grid(True, alpha=0.2, color='#333333', linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='#0a0a0a', edgecolor='none')
    plt.close()
    
    print(f"✅ Cluster visualization saved: {output_path} ({n_clusters} clusters)")


def plot_cluster_statistics(data, output_path):
    """
    Generate bar chart showing cluster weights and statistics
    Handles dynamic number of clusters
    """
    gmm_data = data['gmm']
    weights = np.array(gmm_data['weights'])
    idle_iterations = np.array(gmm_data['idle_iterations'])
    
    n_clusters = len(weights)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('#0a0a0a')
    
    # Dynamic color palette
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, n_clusters))
    
    # Weights bar chart
    ax1.set_facecolor('#1a1a1a')
    bars1 = ax1.bar(
        range(n_clusters), weights, 
        color=colors, edgecolor='white', linewidth=1.5, alpha=0.8
    )
    ax1.set_xlabel('Cluster Index', fontsize=12, color='white', fontweight='bold')
    ax1.set_ylabel('Weight', fontsize=12, color='white', fontweight='bold')
    ax1.set_title(f'Cluster Weights Distribution ({n_clusters} clusters)', 
                  fontsize=14, color='white', fontweight='bold')
    ax1.tick_params(colors='white')
    ax1.spines['bottom'].set_color('#333333')
    ax1.spines['top'].set_color('#333333')
    ax1.spines['left'].set_color('#333333')
    ax1.spines['right'].set_color('#333333')
    ax1.grid(True, alpha=0.2, axis='y', color='#333333')
    
    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width()/2., height,
            f'{height:.2%}', ha='center', va='bottom',
            color='white', fontsize=9, fontweight='bold'
        )
    
    # Idle iterations bar chart
    ax2.set_facecolor('#1a1a1a')
    bars2 = ax2.bar(
        range(n_clusters), idle_iterations,
        color='#ff6b6b', edgecolor='#ff8888', linewidth=1.5, alpha=0.8
    )
    ax2.set_xlabel('Cluster Index', fontsize=12, color='white', fontweight='bold')
    ax2.set_ylabel('Idle Iterations', fontsize=12, color='white', fontweight='bold')
    ax2.set_title(f'Cluster Activity - Idle Iterations ({n_clusters} clusters)', 
                  fontsize=14, color='white', fontweight='bold')
    ax2.tick_params(colors='white')
    ax2.spines['bottom'].set_color('#333333')
    ax2.spines['top'].set_color('#333333')
    ax2.spines['left'].set_color('#333333')
    ax2.spines['right'].set_color('#333333')
    ax2.grid(True, alpha=0.2, axis='y', color='#333333')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='#0a0a0a', edgecolor='none')
    plt.close()
    
    print(f"✅ Cluster statistics saved: {output_path}")


def plot_weight_evolution(output_path):
    """
    Generate line chart showing how cluster weights evolve over time
    HANDLES VARIABLE CLUSTER COUNTS - aligns clusters by tracking max ever seen
    """
    if len(weight_history) < 2:
        return  # Need at least 2 data points
    
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#1a1a1a')
    
    # Find max number of clusters ever seen
    max_clusters = max(len(w) for w in weight_history)
    
    # Pad all weight arrays to same length (fill missing with 0)
    padded_weights = []
    for weights in weight_history:
        padded = np.zeros(max_clusters)
        padded[:len(weights)] = weights
        padded_weights.append(padded)
    
    weights_array = np.array(padded_weights)
    
    # Dynamic color palette based on max clusters
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, max_clusters))
    
    # Plot each cluster's weight over time
    for cluster_idx in range(max_clusters):
        cluster_data = weights_array[:, cluster_idx]
        
        # Only plot if cluster existed at some point
        if np.any(cluster_data > 0):
            ax.plot(
                range(len(weight_history)),
                cluster_data,
                marker='o', linewidth=2, markersize=6,
                label=f'Cluster {cluster_idx}',
                color=colors[cluster_idx],
                alpha=0.8
            )
    
    ax.set_xlabel('Update Iteration', fontsize=12, color='white', fontweight='bold')
    ax.set_ylabel('Weight', fontsize=12, color='white', fontweight='bold')
    ax.set_title(
        f'Cluster Weight Evolution Over Time (Max {max_clusters} clusters)\n'
        f'From {timestamp_history[0]} to {timestamp_history[-1]}',
        fontsize=14, color='white', fontweight='bold', pad=20
    )
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('#333333')
    ax.spines['top'].set_color('#333333')
    ax.spines['left'].set_color('#333333')
    ax.spines['right'].set_color('#333333')
    ax.grid(True, alpha=0.2, color='#333333')
    
    # Place legend outside plot area if too many clusters
    if max_clusters > 8:
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), framealpha=0.9, 
                  facecolor='#1a1a1a', edgecolor='#333333', labelcolor='white')
    else:
        ax.legend(loc='upper left', framealpha=0.9, facecolor='#1a1a1a', 
                  edgecolor='#333333', labelcolor='white')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='#0a0a0a', edgecolor='none', bbox_inches='tight')
    plt.close()
    
    print(f"✅ Weight evolution saved: {output_path}")


def plot_cluster_count_evolution(output_path):
    """
    NEW: Track how the number of clusters changes over time
    """
    if len(cluster_count_history) < 2:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#1a1a1a')
    
    # Plot cluster count over time
    ax.plot(
        range(len(cluster_count_history)),
        cluster_count_history,
        marker='o', linewidth=3, markersize=8,
        color='#00ff88', markerfacecolor='#00ffaa',
        markeredgecolor='white', markeredgewidth=2
    )
    
    # Fill area under curve
    ax.fill_between(
        range(len(cluster_count_history)),
        cluster_count_history,
        alpha=0.3, color='#00ff88'
    )
    
    ax.set_xlabel('Update Iteration', fontsize=12, color='white', fontweight='bold')
    ax.set_ylabel('Number of Clusters', fontsize=12, color='white', fontweight='bold')
    ax.set_title(
        f'Cluster Count Evolution Over Time\n'
        f'From {timestamp_history[0]} to {timestamp_history[-1]}',
        fontsize=14, color='white', fontweight='bold', pad=20
    )
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('#333333')
    ax.spines['top'].set_color('#333333')
    ax.spines['left'].set_color('#333333')
    ax.spines['right'].set_color('#333333')
    ax.grid(True, alpha=0.2, color='#333333')
    
    # Set y-axis to integers only
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    
    # Add min/max annotations
    min_clusters = min(cluster_count_history)
    max_clusters = max(cluster_count_history)
    ax.axhline(y=min_clusters, color='#ff6b6b', linestyle='--', alpha=0.5, linewidth=2)
    ax.axhline(y=max_clusters, color='#4ecdc4', linestyle='--', alpha=0.5, linewidth=2)
    ax.text(0, min_clusters, f' Min: {min_clusters}', va='bottom', color='#ff6b6b', fontweight='bold')
    ax.text(0, max_clusters, f' Max: {max_clusters}', va='top', color='#4ecdc4', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='#0a0a0a', edgecolor='none')
    plt.close()
    
    print(f"✅ Cluster count evolution saved: {output_path}")


def update_visualizations():
    """Main update function called periodically"""
    global last_file_hash, weight_history, cluster_count_history, timestamp_history
    
    # Check if file has changed
    current_hash = compute_file_hash(MODEL_PATH)
    if current_hash is None:
        return
    
    if current_hash == last_file_hash:
        print("⏭️  No changes detected in model file")
        return
    
    last_file_hash = current_hash
    
    # Load model data
    data = load_model_data(MODEL_PATH)
    if data is None:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n🔄 Processing model update at {timestamp}")
    
    # Store weight history and cluster count
    weights = np.array(data['gmm']['weights'])
    n_clusters = len(weights)
    
    weight_history.append(weights)
    cluster_count_history.append(n_clusters)
    timestamp_history.append(datetime.now().strftime("%H:%M:%S"))
    
    # Keep only last 100 entries
    if len(weight_history) > 100:
        weight_history.pop(0)
        cluster_count_history.pop(0)
        timestamp_history.pop(0)
    
    print(f"📊 Current cluster count: {n_clusters}")
    if len(cluster_count_history) > 1:
        prev_count = cluster_count_history[-2]
        if n_clusters > prev_count:
            print(f"   ↗️  INCREASED from {prev_count} (+{n_clusters - prev_count})")
        elif n_clusters < prev_count:
            print(f"   ↘️  DECREASED from {prev_count} ({n_clusters - prev_count})")
        else:
            print(f"   ➡️  No change")
    
    # Generate visualizations
    try:
        # 1. Main cluster visualization (for GIF)
        gif_path = os.path.join(GIF_IMAGES_DIR, f"cluster_{timestamp}.png")
        plot_gmm_clusters(data, gif_path)
        
        # Also save as "latest.png" for easy access
        latest_path = os.path.join(GIF_IMAGES_DIR, "latest.png")
        plot_gmm_clusters(data, latest_path)
        
        # 2. Cluster statistics
        stats_path = os.path.join(CLUSTER_STATS_DIR, f"stats_{timestamp}.png")
        plot_cluster_statistics(data, stats_path)
        
        stats_latest = os.path.join(CLUSTER_STATS_DIR, "latest.png")
        plot_cluster_statistics(data, stats_latest)
        
        # 3. Weight evolution (if we have history)
        if len(weight_history) >= 2:
            evolution_path = os.path.join(WEIGHT_EVOLUTION_DIR, f"evolution_{timestamp}.png")
            plot_weight_evolution(evolution_path)
            
            evolution_latest = os.path.join(WEIGHT_EVOLUTION_DIR, "latest.png")
            plot_weight_evolution(evolution_latest)
        
        # 4. Cluster count evolution (NEW!)
        if len(cluster_count_history) >= 2:
            count_path = os.path.join(CLUSTER_COUNT_DIR, f"count_{timestamp}.png")
            plot_cluster_count_evolution(count_path)
            
            count_latest = os.path.join(CLUSTER_COUNT_DIR, "latest.png")
            plot_cluster_count_evolution(count_latest)
        
        print(f"✨ All visualizations updated successfully!\n")
        
    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()
        print()


def main():
    """Main monitoring loop"""
    print("=" * 70)
    print("🚀 GMM Model Visualization System Started")
    print("=" * 70)
    print(f"📁 Monitoring: {MODEL_PATH}")
    print(f"💾 Output directory: {OUTPUT_DIR}")
    print(f"🔄 Refresh interval: {REFRESH_INTERVAL} seconds")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Features: Dynamic cluster tracking enabled")
    print("=" * 70)
    print("\n👀 Watching for changes...\n")
    
    # Initial update
    update_visualizations()
    
    # Continuous monitoring loop
    try:
        while True:
            time.sleep(REFRESH_INTERVAL)
            update_visualizations()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("🛑 Visualization system stopped by user")
        print(f"📊 Total updates captured: {len(weight_history)}")
        if cluster_count_history:
            print(f"📈 Cluster count range: {min(cluster_count_history)} - {max(cluster_count_history)}")
        print(f"⏰ Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)


if __name__ == "__main__":
    main()
    