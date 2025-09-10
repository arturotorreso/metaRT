#!/bin/bash -ue
kraken2 \
    --use-names \
    --report-minimizer-data \
    --threads 12 \
    --db "/dev/shm" \
    --confidence 0.05 \
    --minimum-base-quality 0 \
    --minimum-hit-groups 2 \
    --memory-mapping \
    --output barcode02.kraken2.tsv \
    --report barcode02.report.tsv \
    barcode02.filtered.fastq.gz

bracken \
    -d "/dev/shm" \
    -i barcode02.report.tsv \
    -o barcode02.bracken_sp.tsv \
    -r 150 \
    -l S
