import json
import pandas as pd
from pathlib import Path


def create_summary_table(summary_file):
    """Create a summary table of model performance metrics by category."""
    
    # Load the summary data
    with open(summary_file, 'r') as f:
        data = json.load(f)
    
    # Prepare data for the table
    rows = []
    
    for model_data in data:
        model_name = model_data['model'].split('/')[-1]  # Use short name
        
        # Add overall performance row
        rows.append({
            'Model': model_name,
            'Category': 'Overall',
            'MRR': f"{model_data['avg_mrr']:.4f}",
            'NDCG': f"{model_data['avg_ndcg']:.4f}",
            'Queries': model_data['queries_evaluated'],
            'Avg Time (ms)': f"{model_data['avg_time_per_abstract_ms']:.2f}"
        })
        
        # Add category-specific performance rows
        for category, metrics in model_data['category_metrics'].items():
            rows.append({
                'Model': model_name,
                'Category': category,
                'MRR': f"{metrics['avg_mrr']:.4f}",
                'NDCG': f"{metrics['avg_ndcg']:.4f}",
                'Queries': metrics['queries_evaluated'],
                'Avg Time (ms)': '-'
            })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Print the table
    print("\n" + "="*100)
    print("MODEL PERFORMANCE SUMMARY BY CATEGORY")
    print("="*100 + "\n")
    print(df.to_string(index=False))
    print("\n" + "="*100 + "\n")
    
    # Create a pivot table for better comparison
    print("\nMRR COMPARISON (by Model and Category)")
    print("-"*100)
    mrr_pivot = df.pivot(index='Category', columns='Model', values='MRR')
    print(mrr_pivot.to_string())
    
    print("\n\nNDCG COMPARISON (by Model and Category)")
    print("-"*100)
    ndcg_pivot = df.pivot(index='Category', columns='Model', values='NDCG')
    print(ndcg_pivot.to_string())
    
    # Save to CSV
    results_dir = Path(summary_file).parent
    output_file = results_dir / 'performance_summary_table.csv'
    df.to_csv(output_file, index=False)
    print(f"\n\nSummary table saved to: {output_file}")
    
    # Also save pivot tables
    mrr_pivot_file = results_dir / 'mrr_comparison.csv'
    ndcg_pivot_file = results_dir / 'ndcg_comparison.csv'
    mrr_pivot.to_csv(mrr_pivot_file)
    ndcg_pivot.to_csv(ndcg_pivot_file)
    print(f"MRR comparison saved to: {mrr_pivot_file}")
    print(f"NDCG comparison saved to: {ndcg_pivot_file}")
    
    # Create ranking table
    print("\n\nMODEL RANKINGS")
    print("="*100)
    
    # Get overall performance only
    overall_df = df[df['Category'] == 'Overall'].copy()
    overall_df['MRR'] = overall_df['MRR'].astype(float)
    overall_df['NDCG'] = overall_df['NDCG'].astype(float)
    
    # Rank by MRR
    overall_df_mrr = overall_df.sort_values('MRR', ascending=False).reset_index(drop=True)
    overall_df_mrr.index = overall_df_mrr.index + 1
    print("\nBy MRR (Mean Reciprocal Rank):")
    print(overall_df_mrr[['Model', 'MRR', 'NDCG', 'Avg Time (ms)']].to_string())
    
    # Rank by NDCG
    overall_df_ndcg = overall_df.sort_values('NDCG', ascending=False).reset_index(drop=True)
    overall_df_ndcg.index = overall_df_ndcg.index + 1
    print("\nBy NDCG (Normalized Discounted Cumulative Gain):")
    print(overall_df_ndcg[['Model', 'NDCG', 'MRR', 'Avg Time (ms)']].to_string())
    
    print("\n" + "="*100 + "\n")
    
    return df


if __name__ == "__main__":
    summary_file = Path(__file__).parent / "results_gpu_20260312_235702" / "summary.json"
    
    if not summary_file.exists():
        print(f"Error: Summary file not found at {summary_file}")
        print("Please provide the correct path to the summary.json file.")
    else:
        create_summary_table(summary_file)
