// modules/local/classification/smart.nf
// This module defines the process for running the SMART classifier.

nextflow.enable.dsl=2

process RUN_SMART {
    tag "SMART on ${sample_id}"
    publishDir "${params.outdir}/3_classification/smart/${sample_id}", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)

    output:
    tuple val(sample_id), path("${sample_id}.smart_reads.csv"), emit: reads_csv
    tuple val(sample_id), path("${sample_id}.smart_summary.csv"), emit: summary_csv

    script:
    """
    run_smart.py ${reads} . ${sample_id} ${params.smart_db}
    """
}
