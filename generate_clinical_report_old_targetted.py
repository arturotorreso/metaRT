# generate_clinical_report.py
import os
import sys
import json
import argparse
import base64
import re
import pandas as pd
from datetime import datetime

# --- CLINICAL CONFIGURATION & THRESHOLDS ---
REPORT_INTERVAL_HOURS = 6
MIN_READS = 50                       # Base evidence floor
MIN_DISTINCT_MINIMIZERS = 5000      # Absolute KrakenUniq threshold for true positives
MIN_AMR_DEPTH = 15                  # Strict minimum depth to call an AMR marker/SNP

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

TARGET_SPECIES = [
    "Staphylococcus aureus", 
    "Enterococcus faecalis", 
    "Enterococcus faecium", 
    "Klebsiella pneumoniae", 
    "Escherichia coli", 
    "Pseudomonas aeruginosa"
]

# Comprehensive Genotype-to-Phenotype Map based on UCLA Antibiogram & AMRrules
AMR_MAP = {
    "Staphylococcus aureus": {
        "Oxacillin / Methicillin": ["mecA", "mecC"],
        "Tetracyclines": ["tet(K)", "tet(M)", "tet(O)", "tetK", "tetM", "tetO"],
        "Clindamycin": ["erm(A)", "erm(C)", "ermA", "ermC"],
        "Trimethoprim-SMX": ["dfr", "sul"],
        "Fluoroquinolones (Cipro)": ["gyrA", "grlA"],
        "Daptomycin": ["mprf mutation", "mprf mutations", "mprf variant"]
    },
    "Enterococcus faecalis": {
        "Vancomycin": ["vanA", "vanB"],
        "High-Level Gentamicin": ["aac(6')", "aph(2'')"],
        "Ampicillin": ["pbp5"]
    },
    "Enterococcus faecium": {
        "Vancomycin": ["vanA", "vanB"],
        "High-Level Gentamicin": ["aac(6')", "aph(2'')"],
        "Ampicillin": ["pbp5"]
    },
    "Klebsiella pneumoniae": {
        "Meropenem / Imipenem": ["blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48", "KPC", "NDM", "VIM", "IMP", "OXA-48"],
        "Ceftriaxone / Cefepime": ["CTX-M", "SHV", "TEM"],
        "Ceftazidime": ["CTX-M", "SHV", "TEM"],
        "Amoxicillin / Cefazolin": ["TEM", "SHV", "OXA-1", "blaTEM", "blaSHV", "blaOXA-1"],
        "Piperacillin": ["blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48", "KPC", "NDM", "VIM", "IMP", "OXA-48", "CTX-M", "SHV", "TEM"],
        "Fluoroquinolones (Cipro)": ["gyrA", "parC", "qnr"],
        "Aminoglycosides (Gent/Tobra)": ["aac(3)", "ant(2'')"],
        "Aminoglycosides (Amikacin)": ["aac(6')-Ib", "armA", "rmtB"],
        "Trimethoprim-SMX": ["sul", "dfr"]
    },
    "Escherichia coli": {
        "Meropenem / Imipenem": ["blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48", "KPC", "NDM", "VIM", "IMP", "OXA-48"],
        "Ceftriaxone / Cefepime": ["CTX-M", "SHV", "TEM"],
        "Ceftazidime": ["CTX-M", "SHV", "TEM"],
        "Amoxicillin / Cefazolin": ["TEM", "SHV", "OXA-1", "blaTEM", "blaSHV", "blaOXA-1"],
        "Piperacillin": ["blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48", "KPC", "NDM", "VIM", "IMP", "OXA-48", "CTX-M", "SHV", "TEM", "blaec-3", "blaec-14", "blaec-15", "blaec-16", "blaec-18"],
        "Fluoroquinolones (Cipro)": ["gyrA", "parC", "qnr"],
        "Aminoglycosides (Gent/Tobra)": ["aac(3)", "ant(2'')"],
        "Aminoglycosides (Amikacin)": ["aac(6')-Ib", "armA", "rmtB"],
        "Trimethoprim-SMX": ["sul", "dfr"]
    },
    "Pseudomonas aeruginosa": {
        "Meropenem / Imipenem": ["blaVIM", "blaIMP", "blaNDM", "blaKPC", "VIM", "IMP", "NDM", "KPC"],
        "Ceftazidime / Cefepime": ["GES", "VEB", "PER"],
        "Piperacillin": ["blaVIM", "blaIMP", "blaNDM", "blaKPC", "VIM", "IMP", "NDM", "KPC", "GES", "VEB", "PER", "ampd", "dacb", "ampr"],
        "Fluoroquinolones (Cipro)": ["gyrA", "parC"],
        "Aminoglycosides (Tobramycin)": ["aac(6')", "ant(2'')"]
    }
}

def should_generate_report(agg_dir, force=False):
    """Checks the hidden state file to see if 6 hours have passed."""
    if force:
        return True, "Forced"
        
    state_file = os.path.join(agg_dir, ".clinical_report_state.json")
    now = datetime.now()
    
    if not os.path.exists(state_file):
        state = {"first_run_time": now.isoformat(), "last_report_hour": 0}
        with open(state_file, 'w') as f:
            json.dump(state, f)
        return False, None
        
    with open(state_file, 'r') as f:
        state = json.load(f)
        
    first_run_time = datetime.fromisoformat(state["first_run_time"])
    elapsed_hours = (now - first_run_time).total_seconds() / 3600.0
    
    current_block = int(elapsed_hours // REPORT_INTERVAL_HOURS) * REPORT_INTERVAL_HOURS
    
    if current_block > 0 and current_block > state.get("last_report_hour", 0):
        state["last_report_hour"] = current_block
        with open(state_file, 'w') as f:
            json.dump(state, f)
        return True, f"Hour_{current_block:02d}"
        
    return False, None

def check_amr_resistance(target_bug, bug_amr_data):
    """Cross-references detected genes with the targeted phenotype map using strict depth filters."""
    if target_bug not in AMR_MAP:
        return {}
        
    # Flatten and sum genes found for this bug, combining chromosome and plasmid evidence
    gene_totals = {}
    for drug_class, genes in bug_amr_data.items():
        for g in genes:
            match = re.search(r'^(.*?)\s*\((\d+)x\)$', g)
            if match:
                name = match.group(1).strip().lower()
                depth = int(match.group(2))
                gene_totals[name] = gene_totals.get(name, 0) + depth
            
    detected_genes = []
    for name, total_depth in gene_totals.items():
        if total_depth >= MIN_AMR_DEPTH:
            detected_genes.append(name)
            
    results = {}
    for antibiotic, markers in AMR_MAP[target_bug].items():
        is_resistant = False
        matching_marker = ""
        
        for marker in markers:
            # Special check for E. coli baseline core blaEC vs variant alleles
            if target_bug == "Escherichia coli" and antibiotic == "Piperacillin" and marker.lower() == "blaec":
                # Ensure it avoids mapping the benign baseline wildtype blaec structural element
                if any(re.search(r'blaec-\d+', d_gene) for d_gene in detected_genes):
                    is_resistant = True
                    matching_marker = "blaEC variant"
                    break
                continue

            pattern = r'(?:^|[^a-z0-9]|bla)' + re.escape(marker.lower()) + r'(?![a-z]{3})'
            if any(re.search(pattern, d_gene) for d_gene in detected_genes):
                is_resistant = True
                matching_marker = marker
                break
                
        if is_resistant:
            results[antibiotic] = ("R", matching_marker)
        else:
            results[antibiotic] = ("S", "")
            
    return results

def generate_html_report(barcode, timestamp_label, detection_results, amr_results, out_dir):
    date_str = datetime.now().strftime("%b-%d-%Y %H:%M")
    report_name = f"PANACIA_Report_{barcode}_{timestamp_label}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    
    icon_path = os.path.join(PROJECT_ROOT, "icon_panacia.png")
    img_tag = ""
    if os.path.exists(icon_path):
        with open(icon_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
        img_tag = f'<img src="data:image/png;base64,{encoded_string}" style="height: 55px; margin-right: 15px;" alt="PANACIA Logo">'

    pathogen_rows = ""
    for bug in TARGET_SPECIES:
        data = detection_results.get(bug)
        if data:
            status = f"<span style='color: #D32F2F; font-weight: bold;'>DETECTED</span>"
            reads = f"{data['reads']:,}"
            pct = f"{data['abundance']:.2f}%"
        else:
            status = "<span style='color: #388E3C;'>Not Detected</span>"
            reads = "--"
            pct = "--"
            
        pathogen_rows += f"""
            <tr>
                <td><em>{bug}</em></td>
                <td>{status}</td>
                <td>{reads}</td>
                <td>{pct}</td>
            </tr>
        """
        
    amr_html = ""
    if amr_results:
        amr_tables_content = ""
        for bug in TARGET_SPECIES:
            if bug in amr_results:
                bug_res = amr_results[bug]
                applicable_drugs = list(AMR_MAP[bug].keys())
                
                th_cols = "".join([f"<th>{drug}</th>" for drug in applicable_drugs])
                
                td_cols = ""
                for drug in applicable_drugs:
                    status, marker = bug_res.get(drug, ("-", ""))
                    if status == "R":
                        td_cols += f"<td style='color: #D32F2F; font-weight: bold;' title='Marker detected: {marker}'>R</td>"
                    else:
                        td_cols += "<td style='color: #555;'>-</td>"
                
                amr_tables_content += f"""
                <div style="margin-top: 25px; margin-bottom: 5px;">
                    <div style="font-size: 15px; font-style: italic; font-weight: 600; margin-bottom: 5px; color: #0e7480; border-bottom: 2px solid #e0e0e0; padding-bottom: 3px; display: inline-block;">
                        {bug}
                    </div>
                    <table class="matrix-table" style="margin-top: 5px;">
                        <tr>{th_cols}</tr>
                        <tr>{td_cols}</tr>
                    </table>
                </div>
                """
                
        amr_html = f"""
        <div class="section-title">TARGETED ANTIBIOGRAM</div>
        {amr_tables_content}
        """

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PANACIA Report | {barcode}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 40px; color: #333; }}
            .header-box {{ border-bottom: 3px solid #0e7480; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
            .title-area {{ display: flex; align-items: center; }}
            .header-box h1 {{ margin: 0; color: #0e7480; font-size: 28px; letter-spacing: 1px; line-height: 1.1; }}
            .meta-info {{ width: 100%; display: flex; justify-content: space-between; background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 30px; font-size: 14px; }}
            .section-title {{ font-size: 16px; font-weight: bold; background: #e0e0e0; padding: 8px 15px; margin-top: 30px; margin-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }}
            th, td {{ border-bottom: 1px solid #ddd; padding: 12px 15px; text-align: left; }}
            th {{ background-color: #fafafa; color: #555; text-transform: uppercase; font-size: 12px; }}
            
            .matrix-table th, .matrix-table td {{ text-align: center; border-right: 1px solid #ddd; border-left: 1px solid #ddd; }}
            
            .footer {{ margin-top: 50px; font-size: 11px; color: #777; text-align: justify; border-top: 1px solid #ddd; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <div class="title-area">
                {img_tag}
                <div>
                    <h1>PANACIA TEST REPORT</h1>
                    <div style="margin-top: 5px; font-size: 14px; color: #666;">CLINICAL METAGENOMICS</div>
                </div>
            </div>
            <div style="text-align: right; font-weight: bold; color: #555; font-size: 14px;">
                Report Time: {timestamp_label}
            </div>
        </div>

        <div class="meta-info">
            <div><strong>Specimen ID:</strong> {barcode}</div>
            <div><strong>Report Generated:</strong> {date_str}</div>
            <div><strong>Specimen Type:</strong> BD BACTEC</div>
        </div>

        <div class="section-title">TARGETED ORGANISM DETECTION</div>
        <table>
            <tr>
                <th>Microorganism Name</th>
                <th>Status</th>
                <th>Read Counts</th>
                <th>Relative Abundance</th>
            </tr>
            {pathogen_rows}
        </table>

        {amr_html}

        <div class="footer">
            <strong>TEST DESCRIPTION</strong><br>
            This targeted report monitors the presence and abundance of specific actionable pathogens using Next-Generation Sequencing (NGS) of microbial genomic DNA. Detection is strictly filtered using absolute distinct minimizer complexities (&gt;{MIN_DISTINCT_MINIMIZERS}) and absolute read counts to prevent false positives from background noise. 
            Antimicrobial resistance genotypic markers are cross-referenced with detected organisms. A result of 'R' indicates genotypic detection of resistance; a '-' implies the marker was not detected, but does not guarantee phenotypic susceptibility. This test has not been cleared or approved by the FDA.
        </div>
    </body>
    </html>
    """
    
    out_path = os.path.join(out_dir, report_name)
    with open(out_path, "w") as f:
        f.write(html_template)
    print(f"Generated report: {out_path}")

def process_batch(agg_dir, force=False):
    should_run, time_label = should_generate_report(agg_dir, force)
    if not should_run:
        return

    print(f"Generating clinical reports for interval: {time_label}")
    
    reports_dir = os.path.join(agg_dir, "clinical_reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    for barcode in os.listdir(agg_dir):
        barcode_path = os.path.join(agg_dir, barcode)
        if not os.path.isdir(barcode_path) or barcode == "clinical_reports":
            continue
            
        tsv_path = os.path.join(barcode_path, f"master_{barcode}.combined_analysis.tsv")
        json_path = os.path.join(barcode_path, f"master_{barcode}.antibiogram.json")
        
        if not os.path.exists(tsv_path):
            continue

        # 1. Filter Species and Calculate True Abundance
        df = pd.read_csv(tsv_path, sep='\t')
        df = df.sort_values('timestamp').drop_duplicates('taxonomy_id', keep='last')
        
        total_sample_reads = df['cumulative_bracken_reads'].sum()
        if total_sample_reads > 0:
            df['true_relative_abundance'] = (df['cumulative_bracken_reads'] / total_sample_reads) * 100
        else:
            df['true_relative_abundance'] = 0.0
        
        valid_hits = df[(df['cumulative_bracken_reads'] >= MIN_READS) & 
                        (df['cumulative_distinct_minimizers'] >= MIN_DISTINCT_MINIMIZERS)]
        
        detection_results = {}
        for _, row in valid_hits.iterrows():
            for target in TARGET_SPECIES:
                if target.lower() in str(row['name']).lower():
                    detection_results[target] = {
                        "reads": row['cumulative_bracken_reads'],
                        "abundance": row['true_relative_abundance']
                    }
                    break

        # 2. Extract AMR Data (Including Plasmid/Mobile Elements)
        amr_results = {}
        if os.path.exists(json_path) and detection_results:
            with open(json_path, 'r') as f:
                amr_data = json.load(f)
                
            for bug in detection_results.keys():
                bug_amr = {}
                for json_org, drug_classes in amr_data.items():
                    # Combine exact bug matches AND Mobile Elements (Plasmids)
                    if bug.lower() in json_org.lower() or json_org == "Unassigned / Mobile Elements":
                        for dc, genes in drug_classes.items():
                            if dc not in bug_amr:
                                bug_amr[dc] = []
                            bug_amr[dc].extend(genes)
                            
                amr_results[bug] = check_amr_resistance(bug, bug_amr)

        # 3. Generate HTML
        generate_html_report(barcode, time_label, detection_results, amr_results, reports_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate targeted clinical reports.")
    parser.add_argument("agg_dir", help="Path to aggregated_results directory")
    parser.add_argument("--force", action="store_true", help="Force generation ignoring the 6-hour timer")
    args = parser.parse_args()
    
    process_batch(args.agg_dir, args.force)