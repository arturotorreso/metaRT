# plotting/abundance_barplots.py
import sys
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

def generate_abundance_plots(aggregated_dir: str, output_dir: str):
    """
    Generates stacked bar plots for absolute and relative abundance across all barcodes.
    """
    bracken_files = glob.glob(os.path.join(aggregated_dir, "*", "master_*.bracken_sp.tsv"))
    if not bracken_files:
        print("No master bracken files found to plot.", file=sys.stderr)
        return

    all_data = []
    for f in bracken_files:
        try:
            barcode_id = os.path.basename(f).replace('master_', '').replace('.bracken_sp.tsv', '')
            df = pd.read_csv(f, sep='\t')
            df['barcode'] = barcode_id
            all_data.append(df)
        except Exception as e:
            print(f"Could not process file {f}: {e}", file=sys.stderr)
            
    if not all_data:
        print("Could not read any bracken files.", file=sys.stderr)
        return

    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Get top 15 species across all samples for better visualization
    top_species = combined_df.groupby('name')['new_est_reads'].sum().nlargest(15).index
    plot_df = combined_df[combined_df['name'].isin(top_species)]

    # Pivot table for plotting
    pivot_df = plot_df.pivot(index='barcode', columns='name', values='new_est_reads').fillna(0)

    # --- Absolute Abundance Plot ---
    fig, ax1 = plt.subplots(figsize=(14, 8))
    pivot_df.plot(kind='bar', stacked=True, ax=ax1, colormap='tab20')
    ax1.set_title('Absolute Abundance of Top Species')
    ax1.set_xlabel('Barcode')
    ax1.set_ylabel('Estimated Read Count')
    ax1.legend(title='Species', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45, ha='right')
    fig.tight_layout()
    abs_path = os.path.join(output_dir, "absolute_abundance_barplot.png")
    fig.savefig(abs_path)
    plt.close(fig)
    print(f"Saved absolute abundance plot to {abs_path}")

    # --- Relative Abundance Plot ---
    relative_df = pivot_df.div(pivot_df.sum(axis=1), axis=0) * 100
    fig, ax2 = plt.subplots(figsize=(14, 8))
    relative_df.plot(kind='bar', stacked=True, ax=ax2, colormap='tab20')
    ax2.set_title('Relative Abundance of Top Species')
    ax2.set_xlabel('Barcode')
    ax2.set_ylabel('Relative Abundance (%)')
    ax2.legend(title='Species', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45, ha='right')
    fig.tight_layout()
    rel_path = os.path.join(output_dir, "relative_abundance_barplot.png")
    fig.savefig(rel_path)
    plt.close(fig)
    print(f"Saved relative abundance plot to {rel_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python abundance_barplots.py <aggregated_results_dir> <output_dir>")
        sys.exit(1)
    generate_abundance_plots(sys.argv[1], sys.argv[2])