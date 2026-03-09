"""
Script to analyze and visualize model data
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def load_model_data(filename='models_large_context.json'):
    """Load model data from JSON file."""
    with open(filename, 'r') as f:
        return json.load(f)


def create_csv(data, filename='models_large_context.csv'):
    """Convert JSON data to CSV."""
    df = pd.DataFrame(data)
    
    # Select relevant columns for CSV
    columns = [
        'model_id', 
        'max_seq_length', 
        'embedding_dim',
        'size_gb',
        'size_str',
        'downloads', 
        'likes',
        'pipeline_tag',
        'description'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in columns if col in df.columns]
    df_export = df[available_columns]
    
    # Sort by downloads
    df_export = df_export.sort_values('downloads', ascending=False)
    
    df_export.to_csv(filename, index=False)
    print(f"CSV saved to {filename}")
    return df_export


def create_visualizations(data):
    """Create visualizations of the model data."""
    df = pd.DataFrame(data)
    
    # Set style
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (15, 10)
    
    # Create subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Size vs Max Seq Length (scatter)
    ax1 = axes[0, 0]
    scatter = ax1.scatter(df['size_gb'], df['max_seq_length'], 
                         c=df['downloads'], cmap='viridis', 
                         s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    ax1.set_xlabel('Model Size (GB)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Max Sequence Length', fontsize=12, fontweight='bold')
    ax1.set_title('Model Size vs Context Length\n(Color = Downloads)', fontsize=14, fontweight='bold')
    ax1.set_xscale('log')
    ax1.grid(True, alpha=0.3)
    cbar1 = plt.colorbar(scatter, ax=ax1)
    cbar1.set_label('Downloads', fontsize=10)
    
    # Add labels for interesting models
    top_models = df.nsmallest(5, 'size_gb')
    for _, row in top_models.iterrows():
        ax1.annotate(row['model_id'].split('/')[-1], 
                    xy=(row['size_gb'], row['max_seq_length']),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=7, alpha=0.7)
    
    # 2. Embedding Dimension Distribution
    ax2 = axes[0, 1]
    dim_counts = df['embedding_dim'].value_counts().sort_index()
    bars = ax2.bar(range(len(dim_counts)), dim_counts.values, 
                   color='steelblue', edgecolor='black', linewidth=1)
    ax2.set_xlabel('Embedding Dimension', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Number of Models', fontsize=12, fontweight='bold')
    ax2.set_title('Distribution of Embedding Dimensions', fontsize=14, fontweight='bold')
    ax2.set_xticks(range(len(dim_counts)))
    ax2.set_xticklabels([f'{int(d)}' if pd.notna(d) else 'N/A' for d in dim_counts.index], rotation=45)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)
    
    # 3. Top 15 models by downloads
    ax3 = axes[1, 0]
    top_downloads = df.nlargest(15, 'downloads')
    bars = ax3.barh(range(len(top_downloads)), top_downloads['downloads'], 
                    color='coral', edgecolor='black', linewidth=1)
    ax3.set_yticks(range(len(top_downloads)))
    ax3.set_yticklabels([m.split('/')[-1] for m in top_downloads['model_id']], fontsize=9)
    ax3.set_xlabel('Downloads', fontsize=12, fontweight='bold')
    ax3.set_title('Top 15 Models by Downloads', fontsize=14, fontweight='bold')
    ax3.invert_yaxis()
    ax3.grid(True, alpha=0.3, axis='x')
    
    # Format x-axis
    ax3.ticklabel_format(style='plain', axis='x')
    
    # 4. Size vs Embedding Dimension
    ax4 = axes[1, 1]
    # Filter out models without embedding_dim
    df_filtered = df[df['embedding_dim'].notna()]
    scatter2 = ax4.scatter(df_filtered['size_gb'], df_filtered['embedding_dim'],
                          c=df_filtered['max_seq_length'], cmap='plasma',
                          s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
    ax4.set_xlabel('Model Size (GB)', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Embedding Dimension', fontsize=12, fontweight='bold')
    ax4.set_title('Model Size vs Embedding Dimension\n(Color = Max Seq Length)', fontsize=14, fontweight='bold')
    ax4.set_xscale('log')
    ax4.grid(True, alpha=0.3)
    cbar2 = plt.colorbar(scatter2, ax=ax4)
    cbar2.set_label('Max Seq Length', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('models_analysis.png', dpi=300, bbox_inches='tight')
    print("Visualization saved to models_analysis.png")
    plt.show()


def print_summary_stats(data):
    """Print summary statistics."""
    df = pd.DataFrame(data)
    
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    print(f"\nTotal models: {len(df)}")
    
    print(f"\nModel Size:")
    print(f"  Min: {df['size_gb'].min():.2f} GB ({df.loc[df['size_gb'].idxmin(), 'model_id']})")
    print(f"  Max: {df['size_gb'].max():.2f} GB ({df.loc[df['size_gb'].idxmax(), 'model_id']})")
    print(f"  Mean: {df['size_gb'].mean():.2f} GB")
    print(f"  Median: {df['size_gb'].median():.2f} GB")
    
    print(f"\nMax Sequence Length:")
    print(f"  Min: {df['max_seq_length'].min()}")
    print(f"  Max: {df['max_seq_length'].max()} ({df.loc[df['max_seq_length'].idxmax(), 'model_id']})")
    print(f"  Mean: {df['max_seq_length'].mean():.0f}")
    print(f"  Median: {df['max_seq_length'].median():.0f}")
    
    if 'embedding_dim' in df.columns:
        df_with_dim = df[df['embedding_dim'].notna()]
        print(f"\nEmbedding Dimension:")
        print(f"  Available for: {len(df_with_dim)} / {len(df)} models")
        if len(df_with_dim) > 0:
            print(f"  Min: {df_with_dim['embedding_dim'].min():.0f}")
            print(f"  Max: {df_with_dim['embedding_dim'].max():.0f}")
            print(f"  Most common: {df_with_dim['embedding_dim'].mode().values[0]:.0f}")
    
    print(f"\nDownloads:")
    print(f"  Total: {df['downloads'].sum():,}")
    print(f"  Mean: {df['downloads'].mean():.0f}")
    print(f"  Most popular: {df.loc[df['downloads'].idxmax(), 'model_id']} ({df['downloads'].max():,})")
    
    print(f"\nTop 5 Smallest Models (<1GB):")
    small_models = df[df['size_gb'] < 1].nsmallest(5, 'size_gb')
    for idx, row in small_models.iterrows():
        print(f"  - {row['model_id']}: {row['size_str']} (dim: {row.get('embedding_dim', 'N/A')}, seq_len: {row['max_seq_length']})")
    
    print(f"\nTop 5 Models with Largest Context (>30K tokens, <2GB):")
    large_context = df[(df['max_seq_length'] > 30000) & (df['size_gb'] < 2)].nlargest(5, 'max_seq_length')
    for idx, row in large_context.iterrows():
        print(f"  - {row['model_id']}: {row['max_seq_length']} tokens, {row['size_str']} (dim: {row.get('embedding_dim', 'N/A')})")


def main():
    """Main function."""
    print("Loading model data...")
    data = load_model_data()
    
    print("\nCreating CSV...")
    df = create_csv(data)
    print(f"Created CSV with {len(df)} models")
    
    print("\nGenerating summary statistics...")
    print_summary_stats(data)
    
    print("\nCreating visualizations...")
    create_visualizations(data)
    
    print("\n" + "="*80)
    print("Analysis complete!")
    print("Files created:")
    print("  - models_large_context.csv")
    print("  - models_analysis.png")
    print("="*80)


if __name__ == "__main__":
    main()
