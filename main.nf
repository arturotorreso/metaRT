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

if (params.help) {
    log.info """
    Usage:
    nextflow run main.nf -profile <wgs,cfdna,16s,docker> --input_dir <path>

    Required Arguments:
    --input_dir         Path to the top-level Nanopore directory.

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
    ch_all_fastqs = Channel.fromPath( "${params.input_dir}/*/*/{fastq_pass,fastq_fail}/barcode*/*.fastq.gz" )
                           .ifEmpty { exit 1, "Cannot find any FASTQ files matching the pattern in: ${params.input_dir}" }

    ch_fastq_files = ch_all_fastqs
        .map { file -> [ file.parent.name, file ] }
        .groupTuple()

    if (params.barcodes) {
        def barcode_list = params.barcodes.split(',').collect { it.trim() }
        ch_fastq_files = ch_fastq_files.filter { barcode, files -> barcode in barcode_list }
    }

    COMBINE_FASTQ(ch_fastq_files)
    ch_input_reads = COMBINE_FASTQ.out.reads

    if (params.run_host_depletion) {
        REMOVE_HOST(ch_input_reads, params.host_opts)
        ch_for_qc = REMOVE_HOST.out.reads
    } else {
        ch_for_qc = ch_input_reads
    }

    if (params.run_read_qc) {
        RUN_QC_FASTPLONG(ch_for_qc, params.qc_opts)
        ch_for_classification = RUN_QC_FASTPLONG.out.reads
    } else {
        ch_for_classification = ch_for_qc
    }

    if (params.run_classification) {
        // Run all classifiers in parallel, based on a new parameter
        // The channel will "fan out" to all selected processes
        if (params.run_kraken) {
            PREPARE_KRAKEN_DB(params.kraken_db, params.kraken_opts)
            RUN_KRAKEN2(
                ch_for_classification,
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