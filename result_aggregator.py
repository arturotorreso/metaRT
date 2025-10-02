# result_aggregator.py
import os
import sys
import subprocess
import logging
import glob
import configparser
import shutil
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from minimizer_tracker import MinimizerTracker
from scipy import stats


# Define the absolute path to the project's root directory based on this script's location
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Check for the combiner script's existence on startup
COMBINE_KREPORTS_PATH = os.path.join(PROJECT_ROOT, 'combine_kreports.py')
if not os.path.exists(COMBINE_KREPORTS_PATH):
    print(f"ERROR: Could not find 'combine_kreports.py' at the expected path: {COMBINE_KREPORTS_PATH}")
    exit(1)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper functions for file finding and manipulation ---

def _get_barcodes_in_batch(batch_result_dir: str) -> list:
    kraken_dir = os.path.join(batch_result_dir, "3_classification", "kraken2")
    if not os.path.isdir(kraken_dir): return []
    return sorted([d for d in os.listdir(kraken_dir) if os.path.isdir(os.path.join(kraken_dir, d))])

def _concatenate_files(source_path: str, destination_path: str):
    if not os.path.exists(source_path):
        logger.warning(f"Source file for concatenation not found: {source_path}")
        return
    try:
        with open(source_path, 'rb') as f_src, open(destination_path, 'ab') as f_dst:
            shutil.copyfileobj(f_src, f_dst)
        logger.info(f"Appended reads to {os.path.basename(destination_path)}")
    except IOError as e:
        logger.error(f"Error concatenating {os.path.basename(source_path)}: {e}")

def _combine_kraken_reports_executable(new_report: str, master_report: str) -> bool:
    if not os.path.exists(new_report):
        logger.warning(f"New report file not found: {new_report}")
        return False
    combiner_script = COMBINE_KREPORTS_PATH # Use the absolute path constant
    temp_output = master_report + ".tmp"
    cmd = []
    if os.path.exists(master_report) and os.path.getsize(master_report) > 0:
        # Use sys.executable to ensure the correct python interpreter is used
        cmd = [sys.executable, combiner_script, "--report-file", master_report, new_report, "--output", temp_output, "--no-headers", "--only-combined"]
    else:
        shutil.copy(new_report, temp_output)
    try:
        if cmd:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        shutil.move(temp_output, master_report)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"combine_kreports.py failed. Stderr:\n{e.stderr}")
        if os.path.exists(temp_output): os.remove(temp_output)
        return False

def _rerun_bracken(master_report_path: str, kraken_db_path: str, output_dir: str, barcode: str, config: configparser.ConfigParser) -> Optional[str]:
    logger.info(f"Re-running Bracken for {barcode}...")
    bracken_output = os.path.join(output_dir, f"master_{barcode}.bracken_sp.tsv")
    read_length = config.getint('KrakenParams', 'read_len', fallback=150)
    command = ["bracken", "-d", kraken_db_path, "-i", master_report_path, "-o", bracken_output, "-r", str(read_length), "-l", "S"]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"Bracken completed successfully for {barcode}.")
        return bracken_output
    except Exception as e:
        logger.error(f"Bracken failed for {barcode}: {e}")
        return None

# --- NEW functions for updating historical data ---

def _update_cumulative_data(bracken_file: str, barcode: str, data_log_path: str):
    """Reads a bracken file and updates the cumulative species data log."""
    now = datetime.now().isoformat()
    try:
        df = pd.read_csv(bracken_file, sep='\t')
        df = df[['name', 'new_est_reads']]
        df['timestamp'] = now
        df['barcode'] = barcode
        df = df.rename(columns={'new_est_reads': 'cumulative_reads'})
        
        # Append to the main data log
        df.to_csv(data_log_path, mode='a', header=not os.path.exists(data_log_path), index=False)
        logger.info(f"Updated cumulative data log for {barcode}")
    except Exception as e:
        logger.error(f"Failed to update cumulative data: {e}")

def _update_rarefaction_data(bracken_file: str, barcode: str, data_log_path: str):
    """Calculates unique species and updates the rarefaction data log."""
    now = datetime.now().isoformat()
    try:
        df = pd.read_csv(bracken_file, sep='\t')
        # Count species with at least one estimated read
        unique_species_count = df[df['new_est_reads'] > 0]['name'].nunique()
        
        new_data = pd.DataFrame([{'timestamp': now, 'barcode': barcode, 'unique_species_count': unique_species_count}])
        new_data.to_csv(data_log_path, mode='a', header=not os.path.exists(data_log_path), index=False)
        logger.info(f"Updated rarefaction data log for {barcode}: {unique_species_count} species.")
    except Exception as e:
        logger.error(f"Failed to update rarefaction data: {e}")


# --- CHANGE: RENAMED FUNCTION AND MODIFIED RETURN VALUE ---
def _calculate_trend(species_history: pd.DataFrame) -> Tuple[float, float]:
    """
    Performs linear regression on the historical data of a single species
    to determine the trend of discovering new distinct minimizers.
    
    Returns:
        A tuple containing the (slope, p_value).
    """
    # We need at least 3 data points to fit a line and get a meaningful result.
    if len(species_history) < 3:
        return 0.0, 1.0  # Default to no slope and non-significant p-value

    # Drop any rows that might have missing data, just in case
    species_history = species_history.dropna(
        subset=['cumulative_bracken_reads', 'cumulative_distinct_minimizers']
    )
    if len(species_history) < 3:
        return 0.0, 1.0

    # Perform the linear regression: X = reads, Y = distinct minimizers
    lin_regress = stats.linregress(
        x=species_history['cumulative_bracken_reads'],
        y=species_history['cumulative_distinct_minimizers']
    )

    # The slope represents the rate of new distinct minimizer discovery
    # The p-value of the slope indicates the significance of the trend.
    return lin_regress.slope, lin_regress.pvalue



# --- Main aggregation function ---

def aggregate_and_plot(batch_result_dir: str, config: configparser.ConfigParser):
    """Main aggregation function. Finds barcodes and aggregates their results individually."""
    if not batch_result_dir or not os.path.isdir(batch_result_dir):
        logger.warning("Batch result directory is invalid. Skipping aggregation.")
        return

    logger.info(f"Starting aggregation for batch: {batch_result_dir}")
    output_dir = config.get('Paths', 'output_directory')
    aggregated_output_dir = os.path.join(output_dir, "aggregated_results")
    os.makedirs(aggregated_output_dir, exist_ok=True)

    if not config.getboolean('WorkflowSteps', 'run_kraken', fallback=False):
        logger.info("run_kraken is false in config; skipping classification aggregation.")
        return

    barcodes = _get_barcodes_in_batch(batch_result_dir)
    if not barcodes:
        logger.warning("No barcode subdirectories found in classification results for this batch.")
        return
        
    logger.info(f"Found batch results for barcodes: {', '.join(barcodes)}")

    # Paths to our historical data logs
    cumulative_data_log = os.path.join(aggregated_output_dir, "cumulative_species_data.csv")
    rarefaction_data_log = os.path.join(aggregated_output_dir, "rarefaction_data.csv")
    
    # Get a single timestamp for the entire batch
    now_timestamp = datetime.now().isoformat()

    # Process each barcode independently
    for barcode in barcodes:
        logger.info(f"--- Processing barcode: {barcode} ---")
        
        barcode_batch_dir = os.path.join(batch_result_dir, "3_classification", "kraken2", barcode)
        barcode_agg_dir = os.path.join(aggregated_output_dir, barcode)
        os.makedirs(barcode_agg_dir, exist_ok=True)

        # 1. Aggregate per-read classifications (master *.kraken2.tsv)
        new_kraken_tsv = os.path.join(barcode_batch_dir, f"{barcode}.kraken2.tsv")
        master_kraken_tsv = os.path.join(barcode_agg_dir, f"master_{barcode}.kraken2.tsv")
        _concatenate_files(new_kraken_tsv, master_kraken_tsv)

        # 2. Combine kraken reports (master *.report.tsv)
        new_report_tsv = os.path.join(barcode_batch_dir, f"{barcode}.report.tsv")
        master_report_tsv = os.path.join(barcode_agg_dir, f"master_{barcode}.report.tsv")
        
        if _combine_kraken_reports_executable(new_report_tsv, master_report_tsv):
            # 3. If report combination successful, re-run Bracken
            kraken_db_path = config.get('DatabasePaths', 'kraken_db')
            final_bracken_output = _rerun_bracken(master_report_tsv, kraken_db_path, barcode_agg_dir, barcode, config)

            # 4. If Bracken successful, run analysis
            if final_bracken_output:
                try:
                    logger.info(f"--- Generating combined analysis for {barcode} ---")
                    
                    taxonomy_dir = config.get('DatabasePaths', 'taxonomy_dir')
                    taxonomy_path = os.path.join(taxonomy_dir, "nodes.dmp")
                    state_file_path = os.path.join(barcode_agg_dir, "minimizer_state.json")
                    raw_minimizer_file = os.path.join(barcode_batch_dir, f"{barcode}.minimizers.tsv")
                    
                    tracker = MinimizerTracker(taxonomy_path=taxonomy_path, state_path=state_file_path)
                    tracker.update_with_batch(raw_minimizer_file=raw_minimizer_file)
                    
                    # Generate the confidence report for the CURRENT batch
                    current_report_df = tracker.generate_confidence_report(
                        bracken_report_file=final_bracken_output,
                        timestamp=now_timestamp 
                    )
                    
                    if current_report_df.empty:
                        logger.warning(f"No species-level data for {barcode} in this batch. Analysis not updated.")
                        continue

                    # Load historical data for p-value calculation
                    combined_report_path = os.path.join(barcode_agg_dir, f"master_{barcode}.combined_analysis.tsv")
                    historical_df = pd.DataFrame()
                    if os.path.exists(combined_report_path):
                        historical_df = pd.read_csv(combined_report_path, sep='\t')

                    # --- CHANGE: CALCULATE SLOPE AND P-VALUE ---
                    slopes = []
                    p_values = []
                    for _, current_row in current_report_df.iterrows():
                        taxid = current_row['taxonomy_id']
                        
                        species_history = pd.DataFrame()
                        # Only search history if the historical DataFrame is not empty
                        if not historical_df.empty:
                            species_history = historical_df[historical_df['taxonomy_id'] == taxid]
                        
                        # Combine historical data with the current data point for regression
                        full_history = pd.concat([species_history, pd.DataFrame([current_row])], ignore_index=True)
                        slope, p_value = _calculate_trend(full_history)
                        slopes.append(slope)
                        p_values.append(p_value)

                    # Add the new columns to the current report
                    current_report_df['regression_slope'] = slopes
                    current_report_df['p_value'] = p_values

                    # --- CHANGE: DEFINE FINAL COLUMN ORDER ---
                    cols_order = [
                        'timestamp', 'name', 'taxonomy_id', 
                        'cumulative_bracken_reads', 'cumulative_total_minimizers', 'cumulative_distinct_minimizers',
                        'diversity_ratio', 'abundance_pct', 'complexity_pct', 'confidence_score',
                        'regression_slope', 'p_value'
                    ]
                    final_df = current_report_df[cols_order]

                    final_df.to_csv(
                        combined_report_path, 
                        sep='\t', 
                        index=False, 
                        mode='a', 
                        header=not os.path.exists(combined_report_path)
                    )
                    logger.info(f"Appended combined analysis report to {combined_report_path}")

                    tracker.save_state()
                    
                except Exception as e:
                    logger.error(f"Analysis failed for {barcode}: {e}", exc_info=True)
                
                # Update other historical data files
                _update_cumulative_data(final_bracken_output, barcode, cumulative_data_log)
                _update_rarefaction_data(final_bracken_output, barcode, rarefaction_data_log)

                # Regenerate cumulative plot for this barcode
                cumulative_script = os.path.join(PROJECT_ROOT, "plotting", "cumulative_plot.py")
                # subprocess.run(["python", os.path.join("plotting", "cumulative_plot.py"), cumulative_data_log, barcode, barcode_agg_dir])
                subprocess.run([sys.executable, cumulative_script, cumulative_data_log, barcode, barcode_agg_dir])
    # After all barcodes are processed, update summary plots
    if barcodes:
        logger.info("--- Updating summary plots for all barcodes ---")

        abundance_script = os.path.join(PROJECT_ROOT, "plotting", "abundance_barplots.py")
        subprocess.run([sys.executable, abundance_script, aggregated_output_dir, aggregated_output_dir])

        rarefaction_script = os.path.join(PROJECT_ROOT, "plotting", "rarefaction_plot.py")
        subprocess.run([sys.executable, rarefaction_script, rarefaction_data_log, aggregated_output_dir])