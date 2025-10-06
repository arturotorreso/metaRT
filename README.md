# metaRT


############## THIS IS ALL DONE ##############
Phase 1: Migrating the Core Pipeline to Nextflow
The goal of this phase is to replace the bash-script orchestration (main_pipeline.sh) with a robust and parallelizable Nextflow workflow. The pipeline will still be run as a single command at this stage.

Task 1.1: Environment and Configuration

Set up a development environment with Nextflow installed - DONE

Create a centralized nextflow.config file to manage all parameters (database paths, threads, tool options) that are currently handled by command-line flags in your scripts. This makes the pipeline easier to configure - DONE

Task 1.2: Convert Scripts to Nextflow Processes (DONE)

Create a main.nf Nextflow script (DONE)

Define a process for Host Depletion that takes a FASTQ file as input and uses remove_host.sh in its script block (DONE)

Define a process for Read QC that takes the output from host depletion and uses run_filtering.sh (DONE)

Define separate process blocks for each Taxonomic Classifier (run_kraken.sh, run_map2refseq_v2.sh, run_smart.py) DONE

Task 1.3: Define the Main Workflow

In main.nf, create the workflow block DONE

Define an input channel that takes a list of FASTQ files (one for each barcode) DONE

Chain the processes together so the output of one step correctly feeds into the input of the next (e.g., QC_channel = READ_QC(HOST_DEPLETION_CHANNEL.out)). DONE

Use conditional logic (e.g., if (params.classifier == 'kraken')) to select which classification process to run. DONE
###############################################



Phase 2: Building the Backend Service and Real-Time Monitor
This phase replaces the direct execution model with a persistent backend service that watches for new files and triggers the Nextflow workflow for new batches of data.

Task 2.1: Develop the Backend Runner

Create a new Python script, nanort_backend.py.

This script will be the main entry point for the service. It will be responsible for parsing the configuration, initializing the file watcher, and launching Nextflow runs.

Task 2.2: Implement the File Watcher and Batching Logic

Integrate your ont_monitoring.py logic into the backend script.

The file watcher will monitor the input directory. When new FASTQ files are detected, it shouldn't trigger immediately. Instead, it should collect file paths for a short period (e.g., 60 seconds) and then group them into a single "batch."

This batch of new files will be passed to the Nextflow workflow for processing. This is inspired by the incremental processing logic in your main_rt.sh but will be more robust.

Task 2.3: Handle Incremental Results and Aggregation

The Nextflow pipeline will now run on small batches of new reads, producing partial results (e.g., a Kraken report for just the new reads).

Create a new Python script (or a Nextflow process) that runs after each batch is processed. Its job is to:

Read the new partial result.

Load the main, aggregated result file.

Append the new data to the main file.

Re-run the plotting scripts (bracken_barplot.py, cummulative_plot.py, etc.) on the newly aggregated data to update the figures.

Phase 3: Evolving the GUI into a Real-Time Dashboard
Here, we'll overhaul the nanoRT_gui.py application, changing it from a static settings panel into an interactive dashboard for monitoring the live pipeline.

Task 3.1: Decouple the GUI

The "Run Pipeline" button will be changed to "Start Monitoring."

When clicked, the GUI will no longer build a long command. Instead, it will:

Write all the user-selected settings into the nextflow.config file.

Launch the nanort_backend.py script as a persistent background process using subprocess.Popen.

Task 3.2: Implement a Status Communication System

The nanort_backend.py service will periodically write its status (e.g., "Monitoring," "Processing batch for barcode01," "Idle") and key statistics (total reads processed) to a structured file, like status.json.

Task 3.3: Build the Dashboard UI

Add a QTimer to the GUI that fires every few seconds.

On each tick, the timer will:

Read the status.json file to update status labels and progress bars.

Reload the output plot images (e.g., the main taxonomy bar chart) into the UI, so the user sees them update live.

Read the latest entries from the main log file and display them in the log window.

Add a "Stop Monitoring" button that gracefully terminates the backend process.

Phase 4: Advanced Features and Packaging
This final phase focuses on making the tool more professional, portable, and powerful by incorporating advanced features from the example projects.

Task 4.1: (Optional) MinKNOW API Integration

Develop a Python module to communicate directly with the MinKNOW gRPC API, using minotourcli as a guide.

Enhance the GUI dashboard to show live metrics fetched from the API, such as run time, pore health, and real-time yield, alongside the analysis results.

Task 4.2: Containerize the Pipeline

Write a Dockerfile that encapsulates all dependencies: Python, Nextflow, and all the bioinformatics tools (Minimap2, Kraken2, Samtools, etc.).

This ensures the pipeline can be run anywhere with Docker, completely solving installation and dependency issues. Nextflow has excellent native support for Docker.

Task 4.3: Robust Database for State Management

Replace the status.json and temporary files with a lightweight SQLite database.

The backend will log all activities, run progress, and file paths to this database. The GUI will query the database to populate its dashboard. This is a much more scalable and robust solution for state management, inspired by the Django models in minotourapp.