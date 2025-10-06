// modules/local/classification/kraken2.nf
nextflow.enable.dsl=2

process RUN_KRAKEN2 {
    tag "Kraken2 on ${sample_id}"
    publishDir "${params.outdir}/3_classification/kraken2/${sample_id}", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    val done_signal
    val kraken_opts

    output:
    tuple val(sample_id), path("${sample_id}.kraken2.tsv"), emit: kraken_out
    tuple val(sample_id), path("${sample_id}.report.tsv"), emit: report
    tuple val(sample_id), path("${sample_id}.minimizers.tsv"), emit: minimizers

    script:
    def final_db_path = kraken_opts.memory_mapping ? '/dev/shm' : params.kraken_db
    def mem_map_flag = kraken_opts.memory_mapping ? '--memory-mapping' : ''

    """
    # This is the core change:
    # 1. The kraken2 command now redirects its standard output (stdout)
    #    to the minimizers file using '>'.
    # 2. The bracken command has been removed.
    ${baseDir}/bin/kraken2 \\
        --use-names \\
        --report-minimizer-data \\
        --threads ${task.cpus} \\
        --db "${final_db_path}" \\
        --confidence ${kraken_opts.confidence} \\
        --minimum-base-quality ${kraken_opts.min_base_q} \\
        --minimum-hit-groups ${kraken_opts.min_hit_groups} \\
        ${mem_map_flag} \\
        --output ${sample_id}.kraken2.tsv \\
        --report ${sample_id}.report.tsv \\
        ${reads} > ${sample_id}.minimizers.tsv
    """
}