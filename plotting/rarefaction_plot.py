# plotting/rarefaction_plot.py
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generate_rarefaction_plot(data_file: str, output_dir: str):
    """
    Generates a rarefaction plot (unique species vs. time) for all barcodes.
    """
    try:
        df = pd.read_csv(data_file)
    except FileNotFoundError:
        print(f"Error: Data file not found at {data_file}", file=sys.stderr)
        return

    if df.empty:
        print(f"No data to plot in {data_file}")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    # --- CHANGE IS HERE: Removed marker='o' ---
    sns.lineplot(data=df, x='timestamp', y='unique_species_count', hue='barcode', ax=ax)
    
    ax.set_title('Species Rarefaction Curve')
    ax.set_xlabel('Time')
    ax.set_ylabel('Number of Unique Species Detected')
    ax.legend(title='Barcode', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.xticks(rotation=30, ha='right')
    fig.tight_layout()

    output_path = os.path.join(output_dir, "rarefaction_curve.png")
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved rarefaction plot to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python rarefaction_plot.py <path_to_data.csv> <output_dir>")
        sys.exit(1)
    generate_rarefaction_plot(sys.argv[1], sys.argv[2])