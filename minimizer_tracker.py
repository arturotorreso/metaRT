import os
import json
import logging
import pandas as pd
from scipy.stats import percentileofscore

logger = logging.getLogger(__name__)

class MinimizerTracker:
    """
    Manages cumulative minimizer counts and generates confidence scores
    by aligning minimizer data with a Bracken abundance estimation report.
    """
    def __init__(self, taxonomy_path: str, state_path: str):
        self.state_path = state_path
        self.parent_map = {}
        self._load_taxonomy(taxonomy_path)

        self.total_minimizers = {}
        self.distinct_minimizers = {}
        self._load_state()

    def _load_taxonomy(self, taxonomy_path: str):
        """Parses a nodes.dmp file to build the parent-child taxonomy map."""
        logger.info(f"Reading taxonomy from {taxonomy_path}...")
        try:
            with open(taxonomy_path, 'r') as f:
                for line in f:
                    parts = line.split('\t|\t')
                    child_id = int(parts[0].strip())
                    parent_id = int(parts[1].strip())
                    self.parent_map[child_id] = parent_id
            logger.info("Taxonomy parsing complete.")
        except FileNotFoundError:
            logger.error(f"Taxonomy file not found at '{taxonomy_path}'. Cannot proceed.")
            raise

    def _load_state(self):
        """Loads the cumulative minimizer counts from a JSON state file."""
        if os.path.exists(self.state_path):
            logger.info(f"Loading minimizer state from {self.state_path}")
            try:
                with open(self.state_path, 'r') as f:
                    state_data = json.load(f)
                    self.total_minimizers = {int(k): v for k, v in state_data.get('total_minimizers', {}).items()}
                    self.distinct_minimizers = {int(k): set(map(int, v)) for k, v in state_data.get('distinct_minimizers', {}).items()}
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load state file, starting fresh. Error: {e}")
        else:
            logger.info("No state file found, starting with a fresh state.")

    def save_state(self):
        """Saves the current cumulative minimizer counts to the state file."""
        logger.info(f"Saving minimizer state to {self.state_path}")
        try:
            serializable_distinct = {k: list(v) for k, v in self.distinct_minimizers.items()}
            state_data = {
                'total_minimizers': self.total_minimizers,
                'distinct_minimizers': serializable_distinct
            }
            with open(self.state_path, 'w') as f:
                json.dump(state_data, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save state file: {e}")

    def update_with_batch(self, raw_minimizer_file: str):
        """Processes a new batch of raw minimizers."""
        logger.info(f"Updating direct hit counts with new batch from {raw_minimizer_file}...")
        minimizers_added = 0
        try:
            with open(raw_minimizer_file, 'r') as f:
                for line in f:
                    try:
                        _, taxid_str, minimizer_str = line.strip().split('\t')
                        taxid = int(taxid_str)
                        if taxid == 0: continue
                        
                        minimizer = int(minimizer_str)
                        self.total_minimizers[taxid] = self.total_minimizers.get(taxid, 0) + 1
                        if taxid not in self.distinct_minimizers:
                            self.distinct_minimizers[taxid] = set()
                        self.distinct_minimizers[taxid].add(minimizer)
                        minimizers_added += 1
                    except (ValueError, IndexError):
                        logger.warning(f"Skipping malformed line in minimizer file: {line.strip()}")
            logger.info(f"Processed and added {minimizers_added} raw minimizer hits to state.")
        except FileNotFoundError:
            logger.error(f"Raw minimizer file not found: {raw_minimizer_file}. Cannot update.")

    # V V V V V  THE ONLY CHANGE IS HERE V V V V V
    def generate_confidence_report(self, bracken_report_file: str, timestamp: str) -> pd.DataFrame:
    # ^ ^ ^ ^ ^  THE ONLY CHANGE IS HERE ^ ^ ^ ^ ^
        """
        Generates a confidence report by combining aggregated minimizer data
        with a Bracken abundance estimation file.
        """
        logger.info("Performing clade aggregation for confidence report...")
        
        # --- Efficient Clade Aggregation ---
        clade_total_minimizers = self.total_minimizers.copy()
        clade_distinct_minimizers = {k: v.copy() for k, v in self.distinct_minimizers.items()}
        
        for taxid in sorted(clade_total_minimizers.keys(), reverse=True):
            parent_id = self.parent_map.get(taxid)
            if parent_id and parent_id != taxid:
                clade_total_minimizers[parent_id] = clade_total_minimizers.get(parent_id, 0) + clade_total_minimizers[taxid]
                if taxid in clade_distinct_minimizers:
                    if parent_id not in clade_distinct_minimizers:
                        clade_distinct_minimizers[parent_id] = set()
                    clade_distinct_minimizers[parent_id].update(clade_distinct_minimizers[taxid])

        # --- Marry with Bracken Report ---
        report_data = []
        try:
            bracken_df = pd.read_csv(bracken_report_file, sep='\t')
            species_df = bracken_df[bracken_df['taxonomy_lvl'] == 'S'].copy()
            logger.info(f"Found {len(species_df)} species-level entries in the Bracken report.")

            for _, row in species_df.iterrows():
                taxid = row['taxonomy_id']
                report_data.append({
                    'timestamp': timestamp,
                    'name': row['name'],
                    'taxonomy_id': taxid,
                    'cumulative_bracken_reads': row['new_est_reads'],
                    'cumulative_total_minimizers': clade_total_minimizers.get(taxid, 0),
                    'cumulative_distinct_minimizers': len(clade_distinct_minimizers.get(taxid, set()))
                })

        except (FileNotFoundError, pd.errors.EmptyDataError):
            logger.error(f"Bracken report file not found or is empty: {bracken_report_file}")
            return pd.DataFrame()

        if not report_data:
            return pd.DataFrame()
            
        report_df = pd.DataFrame(report_data)
        
        # --- Scoring Model ---
        report_df['diversity_ratio'] = report_df.apply(
            lambda row: row['cumulative_distinct_minimizers'] / row['cumulative_total_minimizers'] if row['cumulative_total_minimizers'] > 0 else 0,
            axis=1
        )
        report_df['abundance_pct'] = report_df['cumulative_bracken_reads'].rank(pct=True) * 100
        report_df['complexity_pct'] = report_df['diversity_ratio'].rank(pct=True) * 100
        
        WEIGHT_ABUNDANCE = 0.3
        WEIGHT_COMPLEXITY = 0.7
        report_df['confidence_score'] = (WEIGHT_ABUNDANCE * report_df['abundance_pct']) + \
                                        (WEIGHT_COMPLEXITY * report_df['complexity_pct'])
        
        return report_df.sort_values(by='confidence_score', ascending=False)