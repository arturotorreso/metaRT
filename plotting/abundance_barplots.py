# plotting/abundance_barplots.py
import sys
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

def generate_abundance_plots(aggregated_dir: str, output_dir: str):
    """
    Generates stacked bar plots AND a summary CSV for the interactive GUI.
    """
    # 1. Gather all bracken files
    #    Looks for files like: results/aggregated_results/barcodeXX/master_barcodeXX.bracken_sp.tsv
    bracken_files = glob.glob(os.path.join(aggregated_dir, "*", "master_*.bracken_sp.tsv"))
    
    if not bracken_files:
        print("No master bracken files found to plot.", file=sys.stderr)
        return

    all_data = []
    for f in bracken_files:
        try:
            # Extract barcode from filename
            barcode_id = os.path.basename(f).replace('master_', '').replace('.bracken_sp.tsv', '')
            df = pd.read_csv(f, sep='\t')
            
            # Keep only necessary columns for the GUI
            if 'new_est_reads' in df.columns and 'name' in df.columns:
                temp_df = df[['name', 'new_est_reads']].copy()
                temp_df['barcode'] = barcode_id
                all_data.append(temp_df)
        except Exception as e:
            print(f"Could not process file {f}: {e}", file=sys.stderr)
            
    if not all_data:
        print("Could not read any bracken files.", file=sys.stderr)
        return

    # 2. Combine into one master dataframe
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 3. Rename columns to match what the Interactive GUI expects
    combined_df.rename(columns={'new_est_reads': 'absolute_abundance'}, inplace=True)
    
    # 4. Calculate Relative Abundance
    #    Group by barcode to get total reads per sample
    total_reads = combined_df.groupby('barcode')['absolute_abundance'].transform('sum')
    combined_df['relative_abundance'] = (combined_df['absolute_abundance'] / total_reads) * 100
    
    # 5. Save the CSV for the GUI (The Critical Fix)
    #    This creates 'abundance_data.csv' inside 'aggregated_results/'
    csv_path = os.path.join(output_dir, "abundance_data.csv")
    combined_df.to_csv(csv_path, index=False)
    print(f"Saved interactive data to {csv_path}")

    # --- STATIC PLOTTING LOGIC (Legacy Support) ---
    
    # Get top 15 species across all samples for better visualization
    top_species = combined_df.groupby('name')['absolute_abundance'].sum().nlargest(15).index
    plot_df = combined_df[combined_df['name'].isin(top_species)]

    # Pivot table for plotting
    pivot_df = plot_df.pivot(index='barcode', columns='name', values='absolute_abundance').fillna(0)

    # Absolute Abundance PNG
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

    # Relative Abundance PNG
    relative_pivot = pivot_df.div(pivot_df.sum(axis=1), axis=0) * 100
    
    fig, ax2 = plt.subplots(figsize=(14, 8))
    relative_pivot.plot(kind='bar', stacked=True, ax=ax2, colormap='tab20')
    ax2.set_title('Relative Abundance of Top Species')
    ax2.set_xlabel('Barcode')
    ax2.set_ylabel('Relative Abundance (%)')
    ax2.legend(title='Species', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45, ha='right')
    fig.tight_layout()
    rel_path = os.path.join(output_dir, "relative_abundance_barplot.png")
    fig.savefig(rel_path)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python abundance_barplots.py <aggregated_results_dir> <output_dir>")
        sys.exit(1)
    generate_abundance_plots(sys.argv[1], sys.argv[2])