// modules/local/read_qc.nf

nextflow.enable.dsl=2

process RUN_QC_FASTPLONG {
    tag "QC for ${sample_id}"
    publishDir "${params.outdir}/2_quality_control/${sample_id}", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    val qc_opts // This now accepts the map of QC options

    output:
    tuple val(sample_id), path("${sample_id}.filtered.fastq.gz"), emit: reads
    path("*.json"), emit: json
    path("*.html"), emit: html

    script:
    // Reference the parameters from the 'qc_opts' map that was passed in.
    def fastplong_cmd = "fastplong --stdout -i ${reads} -m ${qc_opts.min_mean_q} -q ${qc_opts.min_base_q} -u ${qc_opts.perc_low_qual} -l ${qc_opts.min_length} -j ${sample_id}.filtered.json -h ${sample_id}.filtered.html"
    if (qc_opts.min_length == 0) {
        fastplong_cmd += " -L"
    }
    if (qc_opts.disable_adapters) {
        fastplong_cmd += " -A"
    }
    if (qc_opts.trim5) {
        fastplong_cmd += " -5"
    }
    if (qc_opts.trim3) {
        fastplong_cmd += " -3"
    }
    if (qc_opts.trim5 || qc_opts.trim3) {
        fastplong_cmd += " -W ${qc_opts.window_size} -M ${qc_opts.cut_quality}"
    }
    if (qc_opts.low_complexity) {
        fastplong_cmd += " --low_complexity_filter"
    }
    // if (qc_opts.low_complexity) {
    //     """
    //     ${fastplong_cmd} | \\
    //         bbduk.sh int=f in=stdin.fq out=stdout.fq entropy=${qc_opts.entropy} entropywindow=${qc_opts.entropy_window} entropyk=${qc_opts.entropy_kmer} | \\
    //         gzip > "${sample_id}.filtered.fastq.gz"
    //     """
    // } else {
    //     """
    //     ${fastplong_cmd} | gzip > "${sample_id}.filtered.fastq.gz"
    //     """
    // }
    """
    ${fastplong_cmd} | gzip > "${sample_id}.filtered.fastq.gz"
    """
}
