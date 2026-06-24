// modules/local/host_depletion.nf
nextflow.enable.dsl=2

process REMOVE_HOST {
    tag "Removing host from ${sample_id}"
    publishDir path: { "${params.outdir}/1_host_depletion/${sample_id}" }, mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    val host_opts

    output:
    tuple val(sample_id), path("${sample_id}.noHost.fastq.gz"), emit: reads
    path("*.hostReads.bam"), emit: bam, optional: true

    script:
    if (host_opts.keep_bam) {
        """
        minimap2 -K 50M -t ${task.cpus} -a -x map-ont "${params.host_reference}" "${reads}" | \\
            tee >(samtools view -@ ${task.cpus} -bS - > "${sample_id}.hostReads.bam") | \\
            samtools view -@ ${task.cpus} -f4 -F256 - | \\
            samtools fastq - | gzip > "${sample_id}.noHost.fastq.gz"
        """
    } else {
        """
        minimap2 -K 50M -t ${task.cpus} -a -x map-ont "${params.host_reference}" "${reads}" | \\
            samtools view -@ ${task.cpus} -f4 -F256 - | \\
            samtools fastq - | \\
            gzip > "${sample_id}.noHost.fastq.gz"
        """
    }
}
