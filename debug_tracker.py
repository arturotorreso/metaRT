import os
import re
import json
import logging
import pandas as pd
from scipy.stats import percentileofscore
from functools import lru_cache
import textwrap

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class MinimizerTracker:
    # ... (init, _load_taxonomy, _is_ancestor, _parse_taxid, etc. are unchanged) ...
    def __init__(self, taxonomy_path: str, state_path: str):
        self.state_path = state_path
        self.parent_map = self._load_taxonomy(taxonomy_path)
        self.total_minimizers = {}
        self.distinct_minimizers = {}
    def _load_taxonomy(self, taxonomy_path: str) -> dict:
        parent_of = {}
        logger.info(f"Reading taxonomy from {taxonomy_path}...")
        try:
            with open(taxonomy_path, 'r') as f:
                for line in f:
                    parts = line.split('\t|\t')
                    child_id = int(parts[0].strip())
                    parent_id = int(parts[1].strip())
                    if child_id == 1: parent_id = 0
                    parent_of[child_id] = parent_id
            logger.info("Taxonomy parsing complete.")
            return parent_of
        except FileNotFoundError:
            logger.error(f"Taxonomy file not found at '{taxonomy_path}'.")
            raise
    @lru_cache(maxsize=None)
    def _is_ancestor(self, ancestor_id: int, child_id: int) -> bool:
        current_id = child_id
        if ancestor_id == current_id: return True
        while current_id in self.parent_map and self.parent_map[current_id] != 0:
            current_id = self.parent_map[current_id]
            if current_id == ancestor_id:
                return True
        return False
    def _parse_taxid(self, taxid_field: str) -> int:
        match = re.search(r'\(taxid (\d+)\)', taxid_field)
        if match: return int(match.group(1))
        return int(taxid_field.strip())

    def update_with_batch(self, raw_minimizer_file: str, kraken_out_file: str):
        logger.info("\n--- Starting Batch Update ---")
        final_classifications = {}
        try:
            with open(kraken_out_file, 'r') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    read_id = parts[1]
                    final_taxid = self._parse_taxid(parts[2])
                    final_classifications[read_id] = final_taxid
            logger.info(f"Loaded final classifications: {final_classifications}")
        except FileNotFoundError:
            logger.error(f"Kraken output file not found: {kraken_out_file}.")
            return

        print("-" * 50)
        try:
            with open(raw_minimizer_file, 'r') as f:
                for line in f:
                    read_id, raw_taxid_str, minimizer_val_str = line.strip().split('\t')
                    raw_taxid = int(raw_taxid_str)
                    minimizer_val = int(minimizer_val_str)
                    final_taxid_for_read = final_classifications.get(read_id)
                    
                    print(f"Processing Minimizer: read='{read_id}', raw_hit={raw_taxid}, final_class={final_taxid_for_read}")

                    if not final_taxid_for_read or raw_taxid == 0:
                        print("  -> SKIPPED (Read not classified or raw hit is unclassified)")
                        continue
                    
                    # --- FINAL CORRECTED LOGIC ---
                    # A minimizer is valid if it and the final classification are in the same lineage.
                    # This means one must be an ancestor of the other.
                    is_lineage_hit = self._is_ancestor(final_taxid_for_read, raw_taxid) or \
                                     self._is_ancestor(raw_taxid, final_taxid_for_read)
                    
                    print(f"  -> Checking lineage: {is_lineage_hit}")
                    
                    if is_lineage_hit:
                        # Always attribute the count to the most specific (child) taxon in the pair.
                        child_taxon = raw_taxid if self._is_ancestor(final_taxid_for_read, raw_taxid) else final_taxid_for_read
                        
                        print(f"  -> COUNTED for specific taxon {child_taxon}")
                        self.total_minimizers[child_taxon] = self.total_minimizers.get(child_taxon, 0) + 1
                        if child_taxon not in self.distinct_minimizers:
                            self.distinct_minimizers[child_taxon] = set()
                        self.distinct_minimizers[child_taxon].add(minimizer_val)
                    else:
                        print("  -> SKIPPED (Not in the same lineage)")
        except FileNotFoundError:
            logger.error(f"Raw minimizer file not found: {raw_minimizer_file}.")

    # ... (generate_summary_report and run_test are unchanged) ...
    def generate_summary_report(self, bracken_report_file: str) -> pd.DataFrame:
        report_data = []
        with open(bracken_report_file, 'r') as f:
            next(f)
            for line in f:
                name, tax_id, _, _, _, reads = line.strip().split('\t')
                total_mins = self.total_minimizers.get(int(tax_id), 0)
                distinct_mins = len(self.distinct_minimizers.get(int(tax_id), set()))
                report_data.append({
                    'name': name, 'taxonomy_id': int(tax_id), 'reads': int(reads),
                    'total_minimizers': total_mins, 'distinct_minimizers': distinct_mins
                })
        return pd.DataFrame(report_data)

def run_test():
    nodes_dmp = textwrap.dedent("""
        1	|	1	|	no rank	|
        2	|	1	|	superkingdom	|
        100	|	2	|	genus	|
        101	|	100	|	species	|
        102	|	100	|	species	|
    """).strip()
    kraken_out = textwrap.dedent("""
        C	Read1	Testus vulgaris (taxid 101)	150	101:10 90:5
        C	Read2	Testus (taxid 100)	150	101:4 102:5 1:1
        U	Read3	0	150	
    """).strip()
    raw_minimizers = textwrap.dedent("""
        Read1	101	11111
        Read1	100	22222
        Read1	0	33333
        Read2	101	44444
        Read2	102	55555
        Read3	101	66666
    """).strip()
    bracken_report = textwrap.dedent("""
        name	taxonomy_id	taxonomy_lvl	kraken_assigned_reads	added_reads	new_est_reads
        Testus vulgaris	101	S	1	0	1
        Testus specificus	102	S	0	1	1
    """).strip()
    with open("test_nodes.dmp", "w") as f: f.write(nodes_dmp)
    with open("test_kraken.out", "w") as f: f.write(kraken_out)
    with open("test_minimizers.tsv", "w") as f: f.write(raw_minimizers)
    with open("test_bracken.tsv", "w") as f: f.write(bracken_report)

    tracker = MinimizerTracker(taxonomy_path="test_nodes.dmp", state_path="test_state.json")
    tracker.update_with_batch(raw_minimizer_file="test_minimizers.tsv", kraken_out_file="test_kraken.out")
    
    print("\n--- Final Minimizer Counts ---")
    print("Total:", tracker.total_minimizers)
    print("Distinct:", {k: len(v) for k, v in tracker.distinct_minimizers.items()})

    summary_df = tracker.generate_summary_report(bracken_report_file="test_bracken.tsv")
    print("\n--- Final Summary Report ---")
    print(summary_df)
    
    os.remove("test_nodes.dmp")
    os.remove("test_kraken.out")
    os.remove("test_minimizers.tsv")
    os.remove("test_bracken.tsv")

if __name__ == "__main__":
    run_test()