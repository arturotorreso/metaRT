#!/bin/bash -ue
fastplong --stdout -i barcode01.fastq.gz -m 8 -q 10 -u 40 -l 1000 -j barcode01.filtered.json -h barcode01.filtered.html --low_complexity_filter | gzip > "barcode01.filtered.fastq.gz"
