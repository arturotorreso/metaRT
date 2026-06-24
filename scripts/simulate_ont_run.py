import os
import shutil
import time
import random
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
SOURCE_ROOT = Path("/mnt/Drive20T/ont_data/20250603_JPL_Samples_Rap_Kit/no_sample_id/20250603_1138_MN45557_FBC24299_2c138b3f/fastq_pass")
DEST_ROOT = Path("/var/lib/minknow/data/20250603_JPL_Samples_Rap_Kit/no_sample_id/20250603_1138_MN45557_FBC24299_2c138b3f/fastq_pass")

# Rate settings
BATCH_SIZE = 30        # Number of files to copy per interval
INTERVAL_SECONDS = 60  # 1 minute between batches
INITIAL_DELAY_SECONDS = 60 # 1 minute wait before first batch

def get_all_files(source_dir):
    """
    Recursively find all .fastq (or .fastq.gz) files in the source directory.
    Returns a list of tuples: (full_source_path, relative_path)
    """
    file_list = []
    print(f"Scanning source directory: {source_dir} ...")
    
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if "fastq" in file: # Simple check for fastq files
                full_path = Path(root) / file
                # Get path relative to the source root (e.g., "barcode01/file.fastq")
                relative_path = full_path.relative_to(source_dir)
                file_list.append((full_path, relative_path))
                
    print(f"Found {len(file_list)} files.")
    return file_list

def simulate_run():
    # 1. Gather and Randomize Files
    all_files = get_all_files(SOURCE_ROOT)
    random.shuffle(all_files) # Randomize order to simulate mixed real-time output

    if not all_files:
        print("No files found. Exiting.")
        return
    
    # --- INITIAL DELAY ---
    print("-" * 40)
    print(f"Files ready. Waiting {INITIAL_DELAY_SECONDS} seconds before starting data transfer...")
    print("Time to start your pipeline!")
    print("-" * 40)
    time.sleep(INITIAL_DELAY_SECONDS)

    # 2. Process in Batches
    total_files = len(all_files)
    processed_count = 0
    
    print(f"Starting simulation. Copying {BATCH_SIZE} files every {INTERVAL_SECONDS} seconds.")
    print(f"Source: {SOURCE_ROOT}")
    print(f"Destination: {DEST_ROOT}")
    print("-" * 40)

    try:
        while processed_count < total_files:
            # Slice the next batch of files
            batch = all_files[processed_count : processed_count + BATCH_SIZE]
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Copying batch of {len(batch)} files...")

            for src_path, rel_path in batch:
                # Construct destination path
                dest_path = DEST_ROOT / rel_path
                
                # Ensure the barcode subdirectory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy the file
                shutil.copy2(src_path, dest_path)
                # print(f"  Copied: {rel_path}") # Uncomment for verbose output

            processed_count += len(batch)
            remaining = total_files - processed_count
            print(f"Progress: {processed_count}/{total_files} ({remaining} remaining)")

            if remaining > 0:
                # print(f"Sleeping for {INTERVAL_SECONDS} seconds...\n")
                time.sleep(INTERVAL_SECONDS)
            else:
                print("\nSimulation complete. All files copied.")

    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")

if __name__ == "__main__":
    simulate_run()