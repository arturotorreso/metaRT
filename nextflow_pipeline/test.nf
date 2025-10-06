// test.nf
nextflow.enable.dsl=2

process SAY_HELLO {
    conda "test-env.yml"

    output:
    stdout

    script:
    """
    python --version
    """
}

workflow {
    SAY_HELLO()
    SAY_HELLO.out.view()
}
