# for n in {01..10}; do for i in {1..10}; do seqtk sample /var/lib/minknow/data/Devin_Fresh_vs_Frozen_09_04_2025/no_sample_id/20250904_1756_MN47539_FBD98145_29b433b4/fastq_pass/barcode$n/*_$i.fastq.gz 1000 | gzip > time_exp/sample_id/flowcell_id/fastq_pass/barcode$n/barcode${n}_$i.fastq.gz; done; done



# echo "130191A.t.o" | sudo -S rm -f /dev/shm/*_distrib
# echo "130191A.t.o" | sudo -S rm -f /dev/shm/*.k2d

barcode_list=""


# Loop through barcodes
for i in {01..10}; do
  # Check if the string is not empty to avoid a leading comma
  if [[ -n "$barcode_list" ]]; then
    barcode_list="${barcode_list}," # Add a comma if it's not the first element
  fi
  barcode_list="${barcode_list}barcode${i}" # Append the new barcode

  echo $barcode_list

  if [ $i == '01' ] || [ $i == '02' ] || [ $i == '06' ] || [ $i == '10' ]; then
    echo "running!"
    echo $barcode_list | tr ',' '\n' > ./results/barcode_list.txt
    # { time nextflow run /mnt/Drive20T/scripts/metaRT/main.nf --input_dir /mnt/Drive20T/scripts/metaRT/test_data/time_exp -profile wgs --barcodes $barcode_list; } 2> nf_time_$i.txt
    { time /mnt/Drive20T/scripts/main.sh --ont_dir /mnt/Drive20T/scripts/metaRT/test_data/time_exp --output_dir ./results -b ./results/barcode_list.txt --preset WGS -k --taxonomy kraken; } 2> pipeline_time_$i.txt
  else
    echo "Skipping!"
  fi

  echo Deleting database for next run
  echo "130191A.t.o" | sudo -S rm -f /dev/shm/*_distrib
  echo "130191A.t.o" | sudo -S rm -f /dev/shm/*.k2d
done
