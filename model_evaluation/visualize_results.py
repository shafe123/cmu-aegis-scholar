import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 10

def create_performance_charts(csv_path):
    """Create comprehensive performance visualization charts."""
    
    # Load data
    df = pd.read_csv(csv_path)
    
    # Convert metric columns to numeric
    df['MRR'] = pd.to_numeric(df['MRR'])
    df['NDCG'] = pd.to_numeric(df['NDCG'])
    df['Avg Time (ms)'] = pd.to_numeric(df['Avg Time (ms)'], errors='coerce')
    
    # Get overall performance only
    overall_df = df[df['Category'] == 'Overall'].copy()
    
    # Get category performance (excluding Overall)
    category_df = df[df['Category'] != 'Overall'].copy()
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # 1. Overall Performance Comparison (MRR and NDCG)
    ax1 = plt.subplot(2, 3, 1)
    x = np.arange(len(overall_df))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, overall_df['MRR'], width, label='MRR', alpha=0.8, color='#2E86AB')
    bars2 = ax1.bar(x + width/2, overall_df['NDCG'], width, label='NDCG', alpha=0.8, color='#A23B72')
    
    ax1.set_xlabel('Model')
    ax1.set_ylabel('Score')
    ax1.set_title('Overall Performance: MRR vs NDCG', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(overall_df['Model'], rotation=45, ha='right')
    ax1.legend()
    ax1.set_ylim(0, 1.0)
    ax1.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}',
                    ha='center', va='bottom', fontsize=8)
    
    # 2. Performance by Category (Heatmap for MRR)
    ax2 = plt.subplot(2, 3, 2)
    mrr_pivot = category_df.pivot(index='Category', columns='Model', values='MRR')
    sns.heatmap(mrr_pivot, annot=True, fmt='.3f', cmap='RdYlGn', ax=ax2, 
                cbar_kws={'label': 'MRR Score'}, vmin=0, vmax=1.0)
    ax2.set_title('MRR by Model and Category', fontweight='bold')
    ax2.set_xlabel('')
    ax2.set_ylabel('Category')
    plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
    
    # 3. Performance by Category (Heatmap for NDCG)
    ax3 = plt.subplot(2, 3, 3)
    ndcg_pivot = category_df.pivot(index='Category', columns='Model', values='NDCG')
    sns.heatmap(ndcg_pivot, annot=True, fmt='.3f', cmap='RdYlGn', ax=ax3,
                cbar_kws={'label': 'NDCG Score'}, vmin=0, vmax=1.0)
    ax3.set_title('NDCG by Model and Category', fontweight='bold')
    ax3.set_xlabel('')
    ax3.set_ylabel('Category')
    plt.setp(ax3.get_xticklabels(), rotation=45, ha='right')
    
    # 4. Speed vs Performance Trade-off (MRR)
    ax4 = plt.subplot(2, 3, 4)
    scatter = ax4.scatter(overall_df['Avg Time (ms)'], overall_df['MRR'], 
                         s=200, alpha=0.6, c=range(len(overall_df)), cmap='viridis')
    
    for idx, row in overall_df.iterrows():
        ax4.annotate(row['Model'], 
                    (row['Avg Time (ms)'], row['MRR']),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=8, alpha=0.8)
    
    ax4.set_xlabel('Avg Time per Abstract (ms)')
    ax4.set_ylabel('MRR Score')
    ax4.set_title('Speed vs Performance Trade-off (MRR)', fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(left=0)
    
    # 5. Speed vs Performance Trade-off (NDCG)
    ax5 = plt.subplot(2, 3, 5)
    scatter = ax5.scatter(overall_df['Avg Time (ms)'], overall_df['NDCG'], 
                         s=200, alpha=0.6, c=range(len(overall_df)), cmap='viridis')
    
    for idx, row in overall_df.iterrows():
        ax5.annotate(row['Model'], 
                    (row['Avg Time (ms)'], row['NDCG']),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=8, alpha=0.8)
    
    ax5.set_xlabel('Avg Time per Abstract (ms)')
    ax5.set_ylabel('NDCG Score')
    ax5.set_title('Speed vs Performance Trade-off (NDCG)', fontweight='bold')
    ax5.grid(True, alpha=0.3)
    ax5.set_xlim(left=0)
    
    # 6. Category Performance Breakdown (Grouped Bar Chart)
    ax6 = plt.subplot(2, 3, 6)
    
    # Prepare data for grouped bar chart
    categories = category_df['Category'].unique()
    models = category_df['Model'].unique()
    x = np.arange(len(categories))
    width = 0.8 / len(models)
    
    colors = plt.cm.Set3(np.linspace(0, 1, len(models)))
    
    for i, model in enumerate(models):
        model_data = category_df[category_df['Model'] == model]
        mrr_values = [model_data[model_data['Category'] == cat]['MRR'].values[0] 
                      if len(model_data[model_data['Category'] == cat]) > 0 else 0
                      for cat in categories]
        ax6.bar(x + i * width, mrr_values, width, label=model, alpha=0.8, color=colors[i])
    
    ax6.set_xlabel('Category')
    ax6.set_ylabel('MRR Score')
    ax6.set_title('MRR Performance by Category', fontweight='bold')
    ax6.set_xticks(x + width * (len(models) - 1) / 2)
    ax6.set_xticklabels(categories, rotation=45, ha='right')
    ax6.legend(loc='upper left', fontsize=8, bbox_to_anchor=(1, 1))
    ax6.grid(axis='y', alpha=0.3)
    ax6.set_ylim(0, 1.1)
    
    plt.tight_layout()
    
    # Save figure
    output_path = Path(csv_path).parent / 'performance_charts.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Charts saved to: {output_path}")
    
    plt.show()
    
    # Create a second figure for rankings
    fig2, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Rank by MRR
    overall_sorted_mrr = overall_df.sort_values('MRR', ascending=True)
    axes[0].barh(range(len(overall_sorted_mrr)), overall_sorted_mrr['MRR'], 
                 color='#2E86AB', alpha=0.8)
    axes[0].set_yticks(range(len(overall_sorted_mrr)))
    axes[0].set_yticklabels(overall_sorted_mrr['Model'])
    axes[0].set_xlabel('MRR Score')
    axes[0].set_title('Model Rankings by MRR', fontweight='bold')
    axes[0].set_xlim(0, 1.0)
    axes[0].grid(axis='x', alpha=0.3)
    
    # Add value labels
    for i, (idx, row) in enumerate(overall_sorted_mrr.iterrows()):
        axes[0].text(row['MRR'] + 0.01, i, f"{row['MRR']:.4f}", 
                    va='center', fontsize=9)
    
    # Rank by NDCG
    overall_sorted_ndcg = overall_df.sort_values('NDCG', ascending=True)
    axes[1].barh(range(len(overall_sorted_ndcg)), overall_sorted_ndcg['NDCG'],
                 color='#A23B72', alpha=0.8)
    axes[1].set_yticks(range(len(overall_sorted_ndcg)))
    axes[1].set_yticklabels(overall_sorted_ndcg['Model'])
    axes[1].set_xlabel('NDCG Score')
    axes[1].set_title('Model Rankings by NDCG', fontweight='bold')
    axes[1].set_xlim(0, 1.0)
    axes[1].grid(axis='x', alpha=0.3)
    
    # Add value labels
    for i, (idx, row) in enumerate(overall_sorted_ndcg.iterrows()):
        axes[1].text(row['NDCG'] + 0.01, i, f"{row['NDCG']:.4f}",
                    va='center', fontsize=9)
    
    plt.tight_layout()
    
    # Save second figure
    output_path2 = Path(csv_path).parent / 'model_rankings.png'
    plt.savefig(output_path2, dpi=300, bbox_inches='tight')
    print(f"Rankings chart saved to: {output_path2}")
    
    plt.show()


if __name__ == "__main__":
    csv_path = Path(__file__).parent / "results_gpu_20260312_235702" / "performance_summary_table.csv"
    
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
    else:
        print("Creating performance charts...")
        create_performance_charts(csv_path)
        print("\nDone! Charts created successfully.")
