# plotting/cumulative_plot.py
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

def generate_cumulative_plot(data_file: str, barcode: str, output_dir: str):
    """
    Generates a cumulative plot of species read counts over time for a specific barcode.
    """
    try:
        df = pd.read_csv(data_file)
    except FileNotFoundError:
        print(f"Error: Data file not found at {data_file}", file=sys.stderr)
        return

    barcode_df = df[df['barcode'] == barcode].copy()
    if barcode_df.empty:
        print(f"No data for barcode {barcode} found in {data_file}")
        return
        
    top_species = barcode_df.groupby('name')['cumulative_reads'].max().nlargest(10).index
    plot_df = barcode_df[barcode_df['name'].isin(top_species)]
    
    plot_df['timestamp'] = pd.to_datetime(plot_df['timestamp'])

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    # --- CHANGE IS HERE: Removed marker='o' ---
    sns.lineplot(data=plot_df, x='timestamp', y='cumulative_reads', hue='name', ax=ax)
    
    ax.set_yscale('log')
    ax.set_title(f'Cumulative Species Detection for {barcode}')
    ax.set_xlabel('Time')
    ax.set_ylabel('Cumulative Read Count (Log Scale)')
    ax.legend(title='Species', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.yaxis.get_major_formatter().set_scientific(False)
    ax.yaxis.get_major_formatter().set_useOffset(False)
    
    plt.xticks(rotation=30, ha='right')
    fig.tight_layout()

    output_path = os.path.join(output_dir, f"cumulative_{barcode}.png")
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved cumulative plot to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python cumulative_plot.py <path_to_data.csv> <barcode_id> <output_dir>")
        sys.exit(1)
    generate_cumulative_plot(sys.argv[1], sys.argv[2], sys.argv[3])