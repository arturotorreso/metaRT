# result_aggregator.py
import os
import sys
import subprocess
import logging
import glob
import configparser
import shutil
import gzip
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from minimizer_tracker import MinimizerTracker
from scipy import stats

# --- CONFIGURATION FLAGS ---
# Set to False if you need to keep Nextflow batch folders (Kraken TSVs, BAMs, etc.) for testing/debugging
CLEANUP_BATCH_FOLDERS = True

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
    command = ["bracken", "-d", kraken_db_path, "-i", master_report_path, "-o", bracken_output, "-r", str(read_length), "-l", "S", "-t", "10"]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"Bracken completed successfully for {barcode}.")
        return bracken_output
    except Exception as e:
        logger.error(f"Bracken failed for {barcode}: {e}")
        return None

# --- NEW function for safe, atomic file writing ---
def _safe_write_csv(df: pd.DataFrame, path: str):
    """Atomically writes a dataframe to a CSV file to prevent race conditions."""
    temp_path = path + ".tmp"
    try:
        df.to_csv(temp_path, index=False)
        os.rename(temp_path, path)
        logger.info(f"Safely wrote updated data to {os.path.basename(path)}")
    except Exception as e:
        logger.error(f"Failed to safe-write to {path}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

# --- MODIFIED functions for updating historical data ---

def _update_cumulative_data(bracken_file: str, barcode: str, data_log_path: str):
    """Reads a bracken file and updates the cumulative species data log safely."""
    now = datetime.now().isoformat()
    try:
        # Prepare new data
        new_df = pd.read_csv(bracken_file, sep='\t')
        new_df = new_df[['name', 'new_est_reads']]
        new_df['timestamp'] = now
        new_df['barcode'] = barcode
        new_df = new_df.rename(columns={'new_est_reads': 'cumulative_reads'})
        
        # Read existing data, append new, and safe-write
        existing_df = pd.DataFrame()
        if os.path.exists(data_log_path):
            existing_df = pd.read_csv(data_log_path)
        
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        _safe_write_csv(combined_df, data_log_path)

    except Exception as e:
        logger.error(f"Failed to update cumulative data: {e}")

def _update_rarefaction_data(bracken_file: str, barcode: str, data_log_path: str):
    """Calculates unique species and updates the rarefaction data log safely."""
    now = datetime.now().isoformat()
    try:
        # Prepare new data point
        df = pd.read_csv(bracken_file, sep='\t')
        unique_species_count = df[df['new_est_reads'] > 0]['name'].nunique()
        new_data = pd.DataFrame([{'timestamp': now, 'barcode': barcode, 'unique_species_count': unique_species_count}])
        
        # Read existing data, append new, and safe-write
        existing_df = pd.DataFrame()
        if os.path.exists(data_log_path):
            existing_df = pd.read_csv(data_log_path)
            
        combined_df = pd.concat([existing_df, new_data], ignore_index=True)
        _safe_write_csv(combined_df, data_log_path)
        
        logger.info(f"Updated rarefaction data log for {barcode}: {unique_species_count} species.")
    except Exception as e:
        logger.error(f"Failed to update rarefaction data: {e}")

def _calculate_trend(species_history: pd.DataFrame) -> Tuple[float, float]:
    """
    Performs linear regression on the historical data of a single species
    to determine the trend of discovering new distinct minimizers.
    
    Returns:
        A tuple containing the (slope, p_value).
    """
    if len(species_history) < 3:
        return 0.0, 1.0

    species_history = species_history.dropna(
        subset=['cumulative_bracken_reads', 'cumulative_distinct_minimizers']
    )
    if len(species_history) < 3:
        return 0.0, 1.0

    # Prevent ValueError if all X values are identical
    if species_history['cumulative_bracken_reads'].nunique() <= 1:
        return 0.0, 1.0

    try:
        lin_regress = stats.linregress(
            x=species_history['cumulative_bracken_reads'],
            y=species_history['cumulative_distinct_minimizers']
        )
        return lin_regress.slope, lin_regress.pvalue
    except Exception:
        return 0.0, 1.0

def _update_read_stats(batch_dir: str, barcode: str, agg_dir: str, config: configparser.ConfigParser):
    """Counts reads directly from the pipeline outputs before they are deleted."""
    raw_pattern = os.path.join(batch_dir, "0_combined_fastq", barcode, "*.fastq.gz")
    host_pattern = os.path.join(batch_dir, "1_host_depletion", barcode, "*.fastq.gz")
    qc_pattern = os.path.join(batch_dir, "2_quality_control", barcode, "*.fastq.gz")

    def count_reads_gz(pattern):
        files = glob.glob(pattern)
        count = 0
        for f in files:
            try:
                with gzip.open(f, 'rb') as gz:
                    lines = 0
                    for block in iter(lambda: gz.read(1024 * 1024), b''):
                        lines += block.count(b'\n')
                    count += lines // 4
            except Exception: pass
        return count

    batch_raw = count_reads_gz(raw_pattern)
    batch_host = count_reads_gz(host_pattern)
    batch_qc = count_reads_gz(qc_pattern)

    # Use Kraken2 TSV to perfectly count post-QC reads (1 line = 1 read)
    kraken_tsv = os.path.join(batch_dir, "3_classification", "kraken2", barcode, f"{barcode}.kraken2.tsv")
    if os.path.exists(kraken_tsv):
        try:
            with open(kraken_tsv, 'rb') as f:
                lines = 0
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    lines += block.count(b'\n')
                batch_qc = lines
        except Exception: pass

    # Cascading fallbacks if a step was skipped in the pipeline
    if not config.getboolean('WorkflowSteps', 'run_host_depletion', fallback=False):
        batch_host = batch_raw
    if not config.getboolean('WorkflowSteps', 'run_read_qc', fallback=False):
        batch_qc = batch_host

    stats_path = os.path.join(agg_dir, "read_stats.csv")
    df = pd.read_csv(stats_path) if os.path.exists(stats_path) else pd.DataFrame(columns=['barcode', 'raw', 'host_depleted', 'qc'])

    if barcode in df['barcode'].values:
        df.loc[df['barcode'] == barcode, 'raw'] += batch_raw
        df.loc[df['barcode'] == barcode, 'host_depleted'] += batch_host
        df.loc[df['barcode'] == barcode, 'qc'] += batch_qc
    else:
        new_row = pd.DataFrame([{'barcode': barcode, 'raw': batch_raw, 'host_depleted': batch_host, 'qc': batch_qc}])
        df = pd.concat([df, new_row], ignore_index=True)

    _safe_write_csv(df, stats_path)

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

    cumulative_data_log = os.path.join(aggregated_output_dir, "cumulative_species_data.csv")
    rarefaction_data_log = os.path.join(aggregated_output_dir, "rarefaction_data.csv")
    
    now_timestamp = datetime.now().isoformat()

    for barcode in barcodes:
        logger.info(f"--- Processing barcode: {barcode} ---")
        
        barcode_batch_dir = os.path.join(batch_result_dir, "3_classification", "kraken2", barcode)
        barcode_agg_dir = os.path.join(aggregated_output_dir, barcode)
        os.makedirs(barcode_agg_dir, exist_ok=True)

        new_kraken_tsv = os.path.join(barcode_batch_dir, f"{barcode}.kraken2.tsv")
        master_kraken_tsv = os.path.join(barcode_agg_dir, f"master_{barcode}.kraken2.tsv")
        _concatenate_files(new_kraken_tsv, master_kraken_tsv)

        new_report_tsv = os.path.join(barcode_batch_dir, f"{barcode}.report.tsv")
        master_report_tsv = os.path.join(barcode_agg_dir, f"master_{barcode}.report.tsv")
        
        # --- Tally Read Stats Before Cleanup ---
        try:
            _update_read_stats(batch_result_dir, barcode, aggregated_output_dir, config)
        except Exception as e:
            logger.error(f"Failed to update read stats for {barcode}: {e}")

        if _combine_kraken_reports_executable(new_report_tsv, master_report_tsv):
            kraken_db_path = config.get('DatabasePaths', 'kraken_db')
            final_bracken_output = _rerun_bracken(master_report_tsv, kraken_db_path, barcode_agg_dir, barcode, config)

            if final_bracken_output:
                try:
                    logger.info(f"--- Generating combined analysis for {barcode} ---")
                    
                    # --- NEW DYNAMIC TAXONOMY RESOLUTION ---
                    taxonomy_dir = config.get('DatabasePaths', 'taxonomy_dir', fallback=None)
                    
                    # 1. Did the user specify a valid dir in config?
                    if taxonomy_dir and os.path.exists(os.path.join(taxonomy_dir, "nodes.dmp")):
                        taxonomy_path = os.path.join(taxonomy_dir, "nodes.dmp")
                    else:
                        # 2. Look in standard kraken_db/taxonomy/nodes.dmp
                        # 3. Look in root kraken_db/nodes.dmp
                        # 4. Fallback to the project's internal scripts/kraken2/data/nodes.dmp backup
                        p1 = os.path.join(kraken_db_path, "taxonomy", "nodes.dmp")
                        p2 = os.path.join(kraken_db_path, "nodes.dmp")
                        p3 = os.path.join(PROJECT_ROOT, "scripts", "kraken2", "data", "nodes.dmp")
                        
                        if os.path.exists(p1): taxonomy_path = p1
                        elif os.path.exists(p2): taxonomy_path = p2
                        else: taxonomy_path = p3
                    # ----------------------------------------
                        
                    state_file_path = os.path.join(barcode_agg_dir, "minimizer_state.json")
                    raw_minimizer_file = os.path.join(barcode_batch_dir, f"{barcode}.minimizers.tsv")
                    
                    tracker = MinimizerTracker(taxonomy_path=taxonomy_path, state_path=state_file_path)
                    tracker.update_with_batch(raw_minimizer_file=raw_minimizer_file)
                    
                    current_report_df = tracker.generate_confidence_report(
                        bracken_report_file=final_bracken_output,
                        timestamp=now_timestamp 
                    )
                    
                    if current_report_df.empty:
                        logger.warning(f"No species-level data for {barcode} in this batch. Analysis not updated.")
                        continue

                    combined_report_path = os.path.join(barcode_agg_dir, f"master_{barcode}.combined_analysis.tsv")
                    historical_df = pd.DataFrame()
                    if os.path.exists(combined_report_path):
                        historical_df = pd.read_csv(combined_report_path, sep='\t')

                    slopes = []
                    p_values = []
                    for _, current_row in current_report_df.iterrows():
                        taxid = current_row['taxonomy_id']
                        
                        species_history = pd.DataFrame()
                        if not historical_df.empty:
                            species_history = historical_df[historical_df['taxonomy_id'] == taxid]
                        
                        full_history = pd.concat([species_history, pd.DataFrame([current_row])], ignore_index=True)
                        slope, p_value = _calculate_trend(full_history)
                        slopes.append(slope)
                        p_values.append(p_value)

                    current_report_df['regression_slope'] = slopes
                    current_report_df['p_value'] = p_values

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
                
                # Update interactive plot data files
                _update_cumulative_data(final_bracken_output, barcode, cumulative_data_log)
                _update_rarefaction_data(final_bracken_output, barcode, rarefaction_data_log)

                # Regenerate static cumulative plot for this barcode
                cumulative_script = os.path.join(PROJECT_ROOT, "plotting", "cumulative_plot.py")
                subprocess.run([sys.executable, cumulative_script, cumulative_data_log, barcode, barcode_agg_dir])

                # --- AMR Aggregation ---
                if config.getboolean('WorkflowSteps', 'run_amr', fallback=False):
                    try:
                        batch_amr_dir = os.path.join(batch_result_dir, "3_classification", "amr", barcode)
                        agg_amr_dir = os.path.join(barcode_agg_dir, "amr_batches")
                        os.makedirs(agg_amr_dir, exist_ok=True)
                        
                        # Copy immutable batch text files
                        if os.path.exists(batch_amr_dir):
                            for f in os.listdir(batch_amr_dir):
                                if f.endswith(".txt"):
                                    shutil.copy2(os.path.join(batch_amr_dir, f), os.path.join(agg_amr_dir, f))
                        
                        # Glob all collected amr files
                        all_amr_files = glob.glob(os.path.join(agg_amr_dir, "*.allele_mapping_data.txt"))
                        amr_df_list = []
                        for amr_f in all_amr_files:
                            try:
                                df = pd.read_csv(amr_f, sep='\t')
                                if not df.empty:
                                    amr_df_list.append(df)
                            except Exception as e:
                                logger.warning(f"Failed to read AMR file {amr_f}: {e}")
                                
                        if amr_df_list:
                            master_amr = pd.concat(amr_df_list, ignore_index=True)
                            
                            # Dynamically map RGI column names which vary by version
                            ref_col = next((c for c in ['Reference', 'Reference Sequence', 'Reference Allele', 'Allele'] if c in master_amr.columns), None)
                            cov_col = next((c for c in ['Percent Coverage', 'Percentage Length of Reference Sequence', 'Coverage'] if c in master_amr.columns), None)
                            depth_col = next((c for c in ['Depth', 'Average Depth'] if c in master_amr.columns), None)
                            reads_col = next((c for c in ['All Mapped Reads', 'Mapped Reads', 'Completely Mapped Reads'] if c in master_amr.columns), None)

                            if not ref_col or not cov_col or not depth_col or not reads_col:
                                logger.error(f"Missing required AMR columns. Found: {list(master_amr.columns)}")
                            elif 'AMR Gene Family' in master_amr.columns:
                                # Ensure Reference Sequence is kept for BAM joining
                                group_cols = [c for c in ['AMR Gene Family', 'Drug Class', 'Resistance Mechanism', ref_col] if c in master_amr.columns]
                                
                                agg_amr = master_amr.groupby(group_cols).agg({
                                    reads_col: 'sum',
                                    cov_col: 'mean',
                                    depth_col: 'mean'
                                }).reset_index()
                                
                                min_cov = config.getfloat('AmrParams', 'min_coverage', fallback=80.0)
                                min_depth = config.getfloat('AmrParams', 'min_depth', fallback=2.0)
                                
                                # RGI leaves 'Depth' completely blank in some outputs. Cast to numeric and use reads_col instead.
                                agg_amr[cov_col] = pd.to_numeric(agg_amr[cov_col], errors='coerce').fillna(0)
                                agg_amr[reads_col] = pd.to_numeric(agg_amr[reads_col], errors='coerce').fillna(0)

                                filtered_amr = agg_amr[(agg_amr[cov_col] >= min_cov) & 
                                                       (agg_amr[reads_col] >= min_depth)]
                                                       
                                amr_summary_path = os.path.join(barcode_agg_dir, f"master_{barcode}.amr_summary.csv")
                                _safe_write_csv(filtered_amr, amr_summary_path)
                                logger.info(f"Aggregated AMR data saved to {amr_summary_path}")

                                # --- Batch Read-Level Join (Kraken + AMR BAM) ---
                                batch_kraken_tsv = os.path.join(barcode_batch_dir, f"{barcode}.kraken2.tsv")
                                batch_bam_files = glob.glob(os.path.join(batch_amr_dir, "*.bam"))
                                master_join_path = os.path.join(barcode_agg_dir, f"master_{barcode}.amr_reads.csv")
                                
                                # Ensure absolute path to samtools to bypass PATH drops in non-interactive python shells
                                samtools_bin = os.path.join(PROJECT_ROOT, "nextflow_pipeline", "bin", "conda-env", "bin", "samtools")
                                if not os.path.exists(samtools_bin):
                                    samtools_bin = "samtools"

                                if os.path.exists(batch_kraken_tsv) and batch_bam_files:
                                    try:
                                        k_df = pd.read_csv(batch_kraken_tsv, sep='\t', header=None, usecols=[1, 2], names=['ReadID', 'TaxID'])
                                        
                                        # Clean TaxID: Handle Kraken's '--use-names' flag outputs like 'Staphylococcus aureus (taxid 1280)'
                                        extracted_tax = k_df['TaxID'].astype(str).str.extract(r'taxid (\d+)')
                                        k_df['TaxID'] = extracted_tax[0].fillna(k_df['TaxID'])
                                        
                                        bam_records = []
                                        for bam in batch_bam_files:
                                            # Execute robustly using list arguments instead of shell pipe
                                            res = subprocess.run([samtools_bin, "view", "-F", "4", bam], capture_output=True, text=True)
                                            for line in res.stdout.strip().split('\n'):
                                                parts = line.split('\t')
                                                if len(parts) >= 3:
                                                    bam_records.append({'ReadID': parts[0], 'Allele': parts[2]})
                                        
                                        if bam_records:
                                            bam_df = pd.DataFrame(bam_records)
                                            joined_df = pd.merge(bam_df, k_df, on='ReadID', how='left')
                                            # Coerce the safely extracted string back into an integer
                                            joined_df['TaxID'] = pd.to_numeric(joined_df['TaxID'], errors='coerce').fillna(0).astype(int)
                                            joined_df.to_csv(master_join_path, mode='a', index=False, header=not os.path.exists(master_join_path))
                                    except Exception as e:
                                        logger.warning(f"Failed to join batch reads for Antibiogram: {e}")

                                # --- Generate Antibiogram JSON ---
                                if not filtered_amr.empty:
                                    try:
                                        import json
                                        antibiogram = {}
                                        tax_dict = {0: "Unassigned / Mobile Elements"}
                                        if os.path.exists(master_report_tsv):
                                            rep_df = pd.read_csv(master_report_tsv, sep='\t', header=None, names=['pct', 'reads', 'lreads', 'lvl', 'taxid', 'name'])
                                            tax_dict.update(dict(zip(rep_df['taxid'], rep_df['name'].str.strip())))
                                            
                                        # BRACKEN FILTER: Get validated species names for filtering and strain-rollup
                                        allowed_species_names = set()
                                        if final_bracken_output and os.path.exists(final_bracken_output):
                                            try:
                                                b_df = pd.read_csv(final_bracken_output, sep='\t')
                                                if 'name' in b_df.columns and 'new_est_reads' in b_df.columns:
                                                    allowed_species_names = set(b_df[b_df['new_est_reads'] > 0]['name'].str.strip())
                                            except Exception as e:
                                                logger.warning(f"Could not load Bracken for AMR filtering: {e}")
                                        
                                        if os.path.exists(master_join_path):
                                            # We have BAM files, link directly to Kraken TaxID
                                            amr_reads_df = pd.read_csv(master_join_path)
                                            hit_counts = amr_reads_df.groupby(['TaxID', 'Allele']).size().reset_index(name='count')
                                            
                                            for _, row in hit_counts.iterrows():
                                                allele_str = str(row['Allele'])
                                                matching_amr = filtered_amr[filtered_amr[ref_col].astype(str) == allele_str]
                                                if matching_amr.empty:
                                                    continue 
                                                
                                                raw_taxid = int(row['TaxID'])
                                                tax_name = tax_dict.get(raw_taxid, "Unassigned / Mobile Elements")
                                                
                                                # BRACKEN FILTER & ROLLUP
                                                if raw_taxid != 0 and allowed_species_names:
                                                    is_validated = False
                                                    for b_name in allowed_species_names:
                                                        # Strain string matching: "Klebsiella pneumoniae subsp..." contains "Klebsiella pneumoniae"
                                                        if b_name in tax_name or tax_name in b_name:
                                                            is_validated = True
                                                            tax_name = b_name  # Clean rollup to species level!
                                                            break
                                                    if not is_validated:
                                                        tax_name = "Unassigned / Mobile Elements"

                                                dc_str = matching_amr.iloc[0]['Drug Class']
                                                drug_classes = [c.strip().capitalize() for c in str(dc_str).split(';')]
                                                gene_name = matching_amr.iloc[0]['AMR Gene Family']
                                                
                                                if tax_name not in antibiogram:
                                                    antibiogram[tax_name] = {}
                                                
                                                for dc in drug_classes:
                                                    if dc not in antibiogram[tax_name]:
                                                        antibiogram[tax_name][dc] = set()
                                                    antibiogram[tax_name][dc].add(f"{gene_name} ({row['count']}x)")
                                        else:
                                            # Fallback if no BAM files are found. Assign to Unassigned.
                                            logger.info(f"Fallback AMR mapping engaged for {barcode} (Read-level join missing).")
                                            tax_name = "Unassigned / Mobile Elements"
                                            antibiogram[tax_name] = {}
                                            for _, row in filtered_amr.iterrows():
                                                dc_str = row['Drug Class']
                                                drug_classes = [c.strip().capitalize() for c in str(dc_str).split(';')]
                                                gene_name = row['AMR Gene Family']
                                                reads_count = int(row[reads_col])
                                                
                                                for dc in drug_classes:
                                                    if dc not in antibiogram[tax_name]:
                                                        antibiogram[tax_name][dc] = set()
                                                    antibiogram[tax_name][dc].add(f"{gene_name} ({reads_count}x)")

                                        # Convert sets back to lists for JSON serialization
                                        for org in antibiogram:
                                            for dc in antibiogram[org]:
                                                antibiogram[org][dc] = list(antibiogram[org][dc])
                                                
                                        anti_json_path = os.path.join(barcode_agg_dir, f"master_{barcode}.antibiogram.json")
                                        with open(anti_json_path + '.tmp', 'w') as f:
                                            json.dump(antibiogram, f, indent=2)
                                        os.rename(anti_json_path + '.tmp', anti_json_path)
                                        logger.info(f"Generated Antibiogram JSON for {barcode}")
                                        
                                        # --- NEW: Export Antibiogram as CSV for external viewing ---
                                        all_drug_classes = set()
                                        for org, dc_dict in antibiogram.items():
                                            all_drug_classes.update(dc_dict.keys())
                                        all_drug_classes = sorted(list(all_drug_classes))
                                        
                                        csv_rows = []
                                        # Sort organisms, ensuring Unassigned is at the bottom
                                        unassigned_key = "Unassigned / Mobile Elements"
                                        orgs_sorted = [o for o in sorted(antibiogram.keys()) if o != unassigned_key]
                                        if unassigned_key in antibiogram:
                                            orgs_sorted.append(unassigned_key)
                                            
                                        for org in orgs_sorted:
                                            row = {'Organism': org}
                                            for dc in all_drug_classes:
                                                genes = antibiogram[org].get(dc, [])
                                                row[dc] = " ; ".join(genes) if genes else "-"
                                            csv_rows.append(row)
                                            
                                        if csv_rows:
                                            csv_df = pd.DataFrame(csv_rows)
                                            csv_df = csv_df[['Organism'] + all_drug_classes]
                                            anti_csv_path = os.path.join(barcode_agg_dir, f"master_{barcode}.antibiogram.csv")
                                            _safe_write_csv(csv_df, anti_csv_path)
                                            logger.info(f"Generated Antibiogram CSV for {barcode}")

                                    except Exception as e:
                                        logger.error(f"Failed to generate Antibiogram outputs: {e}")
                    except Exception as e:
                        logger.error(f"AMR Aggregation failed for {barcode}: {e}", exc_info=True)
    
    if barcodes:
        logger.info("--- Updating summary plots for all barcodes ---")

        abundance_script = os.path.join(PROJECT_ROOT, "plotting", "abundance_barplots.py")
        subprocess.run([sys.executable, abundance_script, aggregated_output_dir, aggregated_output_dir])

        rarefaction_script = os.path.join(PROJECT_ROOT, "plotting", "rarefaction_plot.py")
        subprocess.run([sys.executable, rarefaction_script, rarefaction_data_log, aggregated_output_dir])

    # --- BATCH CLEANUP ---
    if CLEANUP_BATCH_FOLDERS:
        try:
            shutil.rmtree(batch_result_dir, ignore_errors=True)
            logger.info(f"Cleaned up batch directory to save space: {batch_result_dir}")
        except Exception as e:
            logger.error(f"Failed to clean up batch directory {batch_result_dir}: {e}")