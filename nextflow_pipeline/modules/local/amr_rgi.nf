// modules/local/amr_rgi.nf
nextflow.enable.dsl=2

process RUN_AMR {
    tag "AMR ${sample_id}"
    publishDir path: { "${params.outdir}/3_classification/amr/${sample_id}" }, mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    path card_db

    output:
    tuple val(sample_id), path("*.allele_mapping_data.txt"), emit: allele_mapping
    tuple val(sample_id), path("*.bam"), emit: bam, optional: true
    tuple val(sample_id), path("*.gene_mapping_data.txt"), emit: gene_mapping, optional: true
    
    script:
    def basename = reads.baseName.replaceAll('.fastq', '').replaceAll('.fq', '')
    """
    # Create output prefix using the fastq base name for immutable batch outputs
    PREFIX="${sample_id}_${basename}"
    READS_ABS=\$(realpath ${reads})
    OUT_ABS=\$(realpath .)
    
    # We cd into the card_db to ensure local db is found, then run rgi bwt
    (cd ${card_db} && \\
    rgi bwt \\
        -1 \${READS_ABS} \\
        -a bwa \\
        -o \${OUT_ABS}/\${PREFIX} \\
        -n ${task.cpus} \\
        --local \\
        --clean)
    """
}