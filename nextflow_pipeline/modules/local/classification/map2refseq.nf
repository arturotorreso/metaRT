// modules/local/classification/map2refseq.nf
nextflow.enable.dsl=2

process RUN_MAP2REFSEQ {
    tag "Mapping ${sample_id}"
    publishDir "${params.outdir}/3_classification/mapping/${sample_id}", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    val mapping_opts

    output:
    tuple val(sample_id), path("${sample_id}.final.bam"), emit: bam
    tuple val(sample_id), path("${sample_id}.final.bam.bai"), emit: index
    tuple val(sample_id), path("${sample_id}.coverage.tsv"), emit: coverage_stats

    script:
    // Ensure we capture coverage stats. 
    // -A outputs all contigs, even those with 0 coverage (useful for NTC comparison)
    """
    minimap2 \
        -a \
        -x map-ont \
        -t ${task.cpus} \
        -N ${mapping_opts.secondary_aligns} \
        --split-prefix ${sample_id}.temp \
        ${params.refseq_db} \
        ${reads} \
        2> ${sample_id}.final.mm2.log | \
        samtools view -b -S - | \
        samtools sort -o ${sample_id}.final.bam

    samtools index ${sample_id}.final.bam

    # Calculate coverage statistics (Breadth & Depth)
    samtools coverage ${sample_id}.final.bam > ${sample_id}.coverage.tsv
    """
}
