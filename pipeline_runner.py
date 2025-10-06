# pipeline_runner.py
import subprocess
import os
import logging
from datetime import datetime
import configparser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_pipeline_for_batch(fastq_files: list, config: configparser.ConfigParser):
    """
    Executes the Nextflow pipeline for a batch of FASTQ files, using all parameters
    from the provided config object and formatting them correctly for the command line.
    """
    if not fastq_files:
        logging.info("No new files in the batch to process.")
        return None

    logging.info(f"Starting pipeline for a batch of {len(fastq_files)} file(s).")

    # --- Setup paths ---
    output_dir = config.get('Paths', 'output_directory')
    nextflow_script = config.get('Paths', 'nextflow_script')
    processed_log_path = config.get('Settings', 'processed_files_log')

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_output_dir = os.path.join(output_dir, f"batch_{timestamp}")
    os.makedirs(batch_output_dir, exist_ok=True)
    input_files_str = ",".join(fastq_files)

    # --- DYNAMIC COMMAND BUILDING (Corrected Logic) ---
    nextflow_exe = config.get('Paths', 'nextflow_executable', fallback='nextflow')

    command = [
        nextflow_exe, "run", nextflow_script,
        "--input_files", input_files_str,
        "--outdir", batch_output_dir
        # "-profile", "conda" 
    ]

    # ==================== ADD THIS BLOCK ====================
    # 0. Add optional barcodes parameter
    # Check if the 'barcodes' option exists in the [Settings] section and has a value.
    if config.has_option('Settings', 'barcodes'):
        barcodes_value = config.get('Settings', 'barcodes')
        if barcodes_value:  # Only add the flag if the string is not empty
            command.extend(['--barcodes', barcodes_value])
            logging.info(f"Filtering for barcodes: {barcodes_value}")
    # ========================================================


    # 1. Add simple key-value parameters (e.g., database paths)
    if config.has_section('DatabasePaths'):
        for param, value in config.items('DatabasePaths'):
            if value:
                command.extend([f"--{param}", value])

    # 2. Add boolean flags for workflow steps
    if config.has_section('WorkflowSteps'):
        for step, should_run in config.items('WorkflowSteps'):
            # Nextflow automatically interprets the presence of the flag as 'true'
            if config.getboolean('WorkflowSteps', step):
                command.append(f"--{step}")
    
    # 3. Add nested parameters using dot notation (e.g., --qc_opts.min_length 1000)
    # This dictionary maps config sections to their corresponding Nextflow 'params' group name.
    map_param_sections = {
        'HostDepletionParams': 'host_opts',
        'QcParams': 'qc_opts',
        'KrakenParams': 'kraken_opts',
        'MappingParams': 'mapping_opts'
    }

    for section, param_group_name in map_param_sections.items():
        if config.has_section(section):
            for key, value in config.items(section):
                # Construct the dot-notation parameter: --<group>.<key> <value>
                # Example: --qc_opts.min_length 1000
                command.extend([f"--{param_group_name}.{key}", value])
            
    # --- END DYNAMIC COMMAND BUILDING ---

    try:
        # The command is now correctly formatted for Nextflow
        logging.info(f"Executing command: {' '.join(command)}")
        # result = subprocess.run(
        #     command,
        #     check=True,
        #     capture_output=True,
        #     text=True
        # )
        # logging.info("Nextflow pipeline completed successfully for the batch.")
        # logging.debug(f"Nextflow stdout:\n{result.stdout}")

        # Output will now stream directly to the console in real-time.
        subprocess.run(
            command,
            check=True,
            text=True
        )

        logging.info("Nextflow pipeline completed successfully for the batch.")
        log_processed_files(fastq_files, processed_log_path)
        return batch_output_dir

    except FileNotFoundError:
        logging.error("'nextflow' command not found. Is Nextflow installed and in your PATH?")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Nextflow pipeline failed with exit code {e.returncode}.")
        # logging.error(f"Nextflow stderr:\n{e.stderr}")
        return None

def log_processed_files(file_list: list, log_file_path: str):
    """Appends a list of successfully processed files to the log."""
    try:
        with open(log_file_path, 'a') as f:
            for file_path in file_list:
                f.write(f"{file_path}\n")
        logging.info(f"Updated processed files log: {log_file_path}")
    except IOError as e:
        logging.error(f"Could not write to processed files log: {e}")
