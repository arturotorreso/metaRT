# nanort_backend.py
import os
import sys
import time
import argparse
import configparser
import logging
from queue import Queue
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import pipeline_runner
import result_aggregator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FastQHandler(FileSystemEventHandler):
    """A handler for file system events that adds new .fastq.gz files to a queue."""
    def __init__(self, file_queue: Queue, processed_files: set):
        super().__init__()
        self.file_queue = file_queue
        self.processed_files = processed_files
        self.pattern = ".fastq.gz"

    def on_created(self, event):
        """Called when a file is created in the monitored directory."""
        if not event.is_directory and event.src_path.endswith(self.pattern):
            file_path = os.path.abspath(event.src_path)
            # Check if we've already processed this file to avoid duplicates on restart
            if file_path not in self.processed_files:
                logger.info(f"New file detected: {os.path.basename(file_path)}")
                self.file_queue.put(file_path)
                self.processed_files.add(file_path) # Add to the set to prevent re-queueing

def start_monitoring(path_to_watch: str, file_queue: Queue, processed_files: set) -> Observer:
    """Creates and starts the file system watcher in a background thread."""
    event_handler = FastQHandler(file_queue, processed_files)
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=True)
    observer.start()
    logger.info(f"File watcher started on directory: {path_to_watch}")
    return observer

def read_processed_files_log(log_file_path: str) -> set:
    """Reads the log of previously processed files to prevent re-running on startup."""
    processed = set()
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r') as f:
                for line in f:
                    processed.add(line.strip())
            logger.info(f"Loaded {len(processed)} previously processed file paths from log.")
        except IOError as e:
            logger.error(f"Could not read processed files log at '{log_file_path}': {e}")
    return processed

def main():
    """Main function to run the backend service."""
    parser = argparse.ArgumentParser(description="NanoRT Backend: Monitors for new Nanopore data and triggers the Nextflow pipeline.")
    parser.add_argument("-c", "--config", default="config.ini", help="Path to the configuration file (default: config.ini).")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: '{args.config}'. Please create it or specify the path with -c.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(args.config)
    
    fastq_dir_to_watch = config.get('Paths', 'fastq_directory')
    output_dir = config.get('Paths', 'output_directory')
    log_filename = config.get('Settings', 'processed_files_log')
    processed_log_path = os.path.join(output_dir, log_filename)
    
    # We will pass the full config object now, but also update the log path in the object itself
    config['Settings']['processed_files_log'] = processed_log_path

    os.makedirs(output_dir, exist_ok=True)


    # ======================== ADD THIS BLOCK ========================
    # This loop waits for the source FASTQ directory to exist before starting the watcher.
    logger.info(f"Checking for watch directory: {fastq_dir_to_watch}")
    while not os.path.isdir(fastq_dir_to_watch):
        logger.warning(f"Directory not found. Waiting 30 seconds before checking again...")
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received while waiting for directory.")
            sys.exit(0)
    logger.info("Watch directory found!")
    # ================================================================


    file_queue = Queue()
    processed_files_set = read_processed_files_log(processed_log_path)
    observer = start_monitoring(config.get('Paths', 'fastq_directory'), file_queue, processed_files_set)

    try:
        logger.info("Backend service is now running. Press Ctrl+C to stop.")
        while True:
            batch_interval = config.getint('Settings', 'batch_interval_seconds')
            logger.info(f"Waiting for {batch_interval} seconds to gather next batch...")
            time.sleep(batch_interval)
            
            current_batch = []
            while not file_queue.empty():
                current_batch.append(file_queue.get())

            if current_batch:
                logger.info(f"Collected a batch of {len(current_batch)} new files. Starting analysis.")
                
                # Pass the entire config object to the runner
                batch_result_directory = pipeline_runner.run_pipeline_for_batch(current_batch, config)

                if batch_result_directory:
                    # Pass the entire config object to the aggregator
                    result_aggregator.aggregate_and_plot(batch_result_directory, config)
                else:
                    logger.error("Skipping result aggregation due to a pipeline failure.")
            else:
                logger.info("No new files detected in this interval.")

    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    finally:
        logger.info("Stopping file watcher...")
        observer.stop()
        observer.join()
        logger.info("Backend service has been shut down gracefully.")


if __name__ == "__main__":
    main()
