// modules/local/combine_fastq.nf
// This module combines multiple FASTQ files for a single sample into one.

nextflow.enable.dsl=2

process COMBINE_FASTQ {
    tag "Combining ${sample_id} files"
    publishDir "${params.outdir}/0_combined_fastq/${sample_id}", mode: 'copy'

    input:
    tuple val(sample_id), path(reads) // 'reads' is a list of files

    output:
    tuple val(sample_id), path("${sample_id}.fastq.gz"), emit: reads

    script:
    """
    cat ${reads.join(' ')} > ${sample_id}.fastq.gz
    """
}