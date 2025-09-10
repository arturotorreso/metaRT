#!/bin/bash -ue
fastplong --stdout -i barcode02.fastq.gz -m 8 -q 10 -u 40 -l 1000 -j barcode02.filtered.json -h barcode02.filtered.html --low_complexity_filter | gzip > "barcode02.filtered.fastq.gz"
