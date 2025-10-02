#!/usr/bin/env nextflow
nextflow.enable.dsl=2

// ====================================================================================
// == Main Pipeline Entry
// ====================================================================================
log.info """
         N A N O - R T    P I P E L I N E (Modular)
         ==========================================
         Input Directory : ${params.input_dir}
         Output Directory: ${params.outdir}
         Barcodes        : ${params.barcodes ?: 'All'}
         Classifier      : ${params.classifier}
         """
         .stripIndent()

// --- Parameter Definitions ---
params.input_files = null // For real-time mode
params.input_dir   = false // For standard mode
params.outdir      = './results'
params.barcodes    = false
params.help        = false

// --- Workflow Step Control ---
params.run_host_depletion  = false
params.run_read_qc         = true
params.run_classification  = true
params.run_kraken = true
params.run_mapping = false
params.run_smart = false


if (params.help) {
    log.info """
    Usage:
    nextflow run main.nf -profile <wgs,cfdna,16s,docker> --input_dir <path>

    Required Arguments:
    --input_dir         Path to the top-level Nanopore directory.
    --input_files       Comma-separated list of .fastq.gz files for a real-time batch run.

    Optional Arguments:
    --outdir            Directory for pipeline results. (Default: ./results)
    --barcodes          Comma-separated list of barcodes to process (e.g., 'barcode01,barcode05').
    """
    .stripIndent()
    exit 0
}

// ====================================================================================
// == MODULE INCLUSION
// ====================================================================================
include { COMBINE_FASTQ }       from './modules/local/combine_fastq'
include { REMOVE_HOST }         from './modules/local/host_depletion'
include { RUN_QC_FASTPLONG }    from './modules/local/read_qc'
include { PREPARE_KRAKEN_DB }   from './modules/local/prepare_kraken_db'
include { RUN_KRAKEN2 }         from './modules/local/classification/kraken2'
include { RUN_MAP2REFSEQ }      from './modules/local/classification/map2refseq'
include { RUN_SMART }           from './modules/local/classification/smart'

// ====================================================================================
// == WORKFLOW DEFINITION
// ====================================================================================
workflow {
    
    // STEP 1: Determine the input source
    if (params.input_files) {
        // --- REAL-TIME MODE (FIXED) ---
        // Split the comma-separated string into a list and create a channel
        def file_list = params.input_files.split(',').collect { it.trim() }
        ch_all_fastqs = Channel.fromList(file_list)
                               .map { file(it) } // Convert string paths to file objects
                               .ifEmpty { exit 1, "The --input_files parameter was empty or invalid." }
    } else if (params.input_dir) {
        // --- STANDARD MODE ---
        // Input is found by scanning the input directory
        ch_all_fastqs = Channel.fromPath( "${params.input_dir}/*/*/{fastq_pass,fastq_fail}/barcode*/*.fastq.gz" )
                               .ifEmpty { exit 1, "Cannot find any FASTQ files in: ${params.input_dir}" }
    } else {
        exit 1, "Please provide an input source with either --input_dir or --input_files"
    }

    ch_fastq_files = ch_all_fastqs
        .map { file -> [ file.parent.name, file ] }
        .groupTuple()

    if (params.barcodes) {
        def barcode_list = params.barcodes.split(',').collect { it.trim() }
        ch_fastq_files = ch_fastq_files.filter { barcode, files -> barcode in barcode_list }
    }

    COMBINE_FASTQ(ch_fastq_files)
    ch_input_reads = COMBINE_FASTQ.out.reads
        .filter { sample_id, reads_file -> reads_file.size() > 100 }

    if (params.run_host_depletion) {
        REMOVE_HOST(ch_input_reads, params.host_opts)
        ch_for_qc = REMOVE_HOST.out.reads
            .filter { sample_id, reads_file -> reads_file.size() > 100 }
    } else {
        ch_for_qc = ch_input_reads
    }

    if (params.run_read_qc) {
        RUN_QC_FASTPLONG(ch_for_qc, params.qc_opts)
        ch_for_classification = RUN_QC_FASTPLONG.out.reads
            .filter { sample_id, reads_file -> reads_file.size() > 100 }
    } else {
        ch_for_classification = ch_for_qc
    }

    if (params.run_classification) {
        // Run all classifiers in parallel, based on a new parameter
        // The channel will "fan out" to all selected processes
        if (params.run_kraken) {
            PREPARE_KRAKEN_DB(params.kraken_db, params.kraken_opts)

            // <-- CHANGED: The logic below is updated
            // Call the process with all three required inputs directly.
            // Nextflow will automatically pair the single 'done' signal
            // with each item from the 'ch_for_classification' channel.
            RUN_KRAKEN2(
                ch_for_classification,
                PREPARE_KRAKEN_DB.out.done,
                params.kraken_opts
            )
        }
        if (params.run_mapping) {
            RUN_MAP2REFSEQ(
                ch_for_classification,
                params.mapping_opts
            )
        }
        if (params.run_smart) {
            RUN_SMART(ch_for_classification)
        }
    }
}