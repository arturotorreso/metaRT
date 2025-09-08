# metaRT

Nextflow Migration Checklist
The Configuration File (nextflow.config)

This will be our single source of truth for all pipeline parameters. We'll extract every path, database location, and tool-specific option (like quality scores or confidence thresholds) from your scripts and centralize them here.

The Main Workflow Script (main.nf) - Skeleton

We'll create the main script and define the overall workflow block. This includes setting up the initial input channel that finds FASTQ files and groups them by barcode, which is the key to our parallelization strategy.

The Core Processes (REMOVE_HOST & FILTER_READS)

We'll convert your first two sequential scripts (remove_host.sh and run_filtering.sh) into Nextflow process blocks inside main.nf. This will give us a functional, albeit incomplete, pipeline.

The Conditional Analysis Processes (Kraken, Mapping, SMART)

Next, we'll convert the three parallel analysis scripts. A key part of this step will be implementing the conditional logic so that each process only runs if its corresponding parameter (e.g., params.run_kraken) is set to true.

Software Dependency Management (Conda)

Once the processes are defined, we'll add the conda directive to each one. This tells Nextflow which specific software tools (like minimap2, samtools, kraken2) are needed for each task, making the pipeline fully reproducible.

Final Touches & Documentation

We'll finish by creating a simple README.md file with clear instructions on how to run the new Nextflow pipeline and modify its parameters using the configuration file.

