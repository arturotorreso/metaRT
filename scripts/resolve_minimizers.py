# --- Pre-computation Steps ---
# 1. You need a way to check if one taxon is an ancestor of another.
#    You can build this from your taxonomy's nodes.dmp file.
#    Example: is_ancestor(parent_taxid, child_taxid) -> True/False
def build_ancestry_map(nodes_dmp_file):
    parent_of = {}
    with open(nodes_dmp_file, 'r') as f:
        for line in f:
            parts = line.split('\t|\t')
            child_id = int(parts[0].strip())
            parent_id = int(parts[1].strip())
            parent_of[child_id] = parent_id
    return parent_of

parent_of = build_ancestry_map('path/to/your/nodes.dmp')

def is_ancestor(ancestor_id, child_id, parent_map):
    """Checks if a taxon is an ancestor of another."""
    current_id = child_id
    while current_id in parent_map and current_id != 0:
        if current_id == ancestor_id:
            return True
        current_id = parent_map[current_id]
    return False

# --- Main Logic ---
# This dictionary will store the sets of unique minimizers for each taxon.
minimizers_per_taxon = {}

# 1. Load the final classifications for each read.
final_classifications = {}
with open('final_kraken_report.tsv', 'r') as f:
    for line in f:
        parts = line.split('\t')
        read_id = parts[1]
        final_taxid = int(parts[2])
        final_classifications[read_id] = final_taxid

# 2. Process your raw minimizer output.
with open('raw_minimizer_output.tsv', 'r') as f:
    for line in f:
        read_id, minimizer_taxid_str, minimizer_value_str = line.strip().split('\t')
        minimizer_taxid = int(minimizer_taxid_str)
        minimizer_value = int(minimizer_value_str)

        if read_id not in final_classifications:
            continue

        final_taxid_for_read = final_classifications[read_id]

        # This is the key filtering step!
        # Only count the minimizer if its raw hit is on the path to the
        # final classification for the read.
        if minimizer_taxid == final_taxid_for_read or \
           is_ancestor(minimizer_taxid, final_taxid_for_read, parent_of):

            if final_taxid_for_read not in minimizers_per_taxon:
                minimizers_per_taxon[final_taxid_for_read] = set()

            minimizers_per_taxon[final_taxid_for_read].add(minimizer_value)

# 3. Aggregate up the tree (mimicking GetCladeCounters).
clade_minimizers = {}
for taxid, minimizer_set in minimizers_per_taxon.items():
    current_id = taxid
    while current_id in parent_of and current_id != 0:
        if current_id not in clade_minimizers:
            clade_minimizers[current_id] = set()
        
        clade_minimizers[current_id].update(minimizer_set)
        current_id = parent_of[current_id]

# Now, `clade_minimizers` holds the accurate sets of unique minimizers for each clade.
# You can get the distinct count for any taxon like this:
# distinct_count = len(clade_minimizers.get(some_taxid, set()))

# This will much more closely replicate the numbers in the Kraken2 report.