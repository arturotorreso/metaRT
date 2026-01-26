// modules/local/classification/amr_rgi.nf
nextflow.enable.dsl=2

process RUN_RGI {
    tag "AMR ${sample_id}"
    publishDir "${params.outdir}/3_classification/amr/${sample_id}", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    path rgi_db_local // Optional: Path to a local CARD JSON/folder if not using container default

    output:
    tuple val(sample_id), path("${sample_id}.rgi.txt"), emit: report
    tuple val(sample_id), path("${sample_id}.rgi.json"), emit: json

    script:
    // -t read: Run in read mapping mode (suitable for metagenomics)
    // -a DIAMOND: Much faster for high-throughput data
    // --low_quality: Important for Nanopore to include reads with partial gene matches
    """
    rgi main \
        --input_sequence ${reads} \
        --output_file ${sample_id}.rgi \
        --input_type read \
        --alignment_tool DIAMOND \
        --num_threads ${task.cpus} \
        --clean \
        --low_quality 
    """
}