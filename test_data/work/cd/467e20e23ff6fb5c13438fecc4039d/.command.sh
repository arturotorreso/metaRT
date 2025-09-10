#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# Redirect all output to a log file for easier debugging
exec > >(tee db_prep.log) 2>&1

check_and_load_db() {
  local original_db="$1"
  local shm_dir="/dev/shm"
  local db_is_ok=true

  echo "Original DB path: $original_db"
  echo "Shared memory path: $shm_dir"

  # Check each essential file from the source DB
  for file in "$original_db"/*.k2d "$original_db"/taxo.dmp; do
    if [ -f "$file" ]; then
        local base_name=$(basename "$file")
        local shm_file="$shm_dir/$base_name"

        if [[ -f "$shm_file" ]]; then
          local original_size=$(stat -c%s "$file")
          local shm_size=$(stat -c%s "$shm_file")

          if [[ "$original_size" -ne "$shm_size" ]]; then
            echo "File '$base_name' has a size mismatch. Deleting and reloading."
            rm "$shm_file"
            db_is_ok=false
          fi
        else
          echo "File '$base_name' is missing from /dev/shm."
          db_is_ok=false
        fi
    fi
  done

  if $db_is_ok; then
    echo "Database already in memory and appears correct."
    echo "$shm_dir"
    return 0
  fi

  echo "Database not fully in memory or is incomplete. Loading..."

  # Check available space before copying
  local db_size=$(du -sb "$original_db" | awk '{print $1}')
  local shm_free=$(df -B1 "$shm_dir" | awk 'NR==2{print $4}')

  if [[ "$db_size" -gt "$shm_free" ]]; then
    echo "Error: Database size ($db_size B) exceeds available space in /dev/shm ($shm_free B)."
    exit 1
  fi

  echo "Copying database files to /dev/shm..."
  rsync -aP "$original_db"/*.k2d "$shm_dir/"
  rsync -aP "$original_db"/*_distrib "$shm_dir/"

  echo "Done loading database!"
  echo "$shm_dir"
  return 0
}

# --- Main logic of the script block ---
if true; then
    echo "Memory mapping is enabled. Checking /dev/shm..."
    check_and_load_db "/mnt/Drive20T/db/kraken2_standard_pluspf"
else
    echo "Memory mapping disabled. Using original DB path."
fi
