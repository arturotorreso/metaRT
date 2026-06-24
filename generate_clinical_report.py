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
MIN_READS = 100                      # Base evidence floor
MIN_DISTINCT_MINIMIZERS = 15000      # Absolute KrakenUniq threshold for true positives
MIN_AMR_DEPTH = 5                  # Strict minimum depth to call an AMR marker/SNP

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

TARGET_SPECIES = [
    "Staphylococcus aureus", 
    "Enterococcus faecalis", 
    "Enterococcus faecium", 
    "Klebsiella pneumoniae", 
    "Escherichia coli", 
    "Pseudomonas aeruginosa"
]

# Broad taxonomic lineages for the Clinical Roll-Down of stranded MGEs/AMR genes
LINEAGE_MAP = {
    "Staphylococcus aureus": ["Staphylococcus", "Bacilli"],
    "Enterococcus faecalis": ["Enterococcus", "Bacilli", "Lactobacillales"],
    "Enterococcus faecium": ["Enterococcus", "Bacilli", "Lactobacillales"],
    "Klebsiella pneumoniae": ["Klebsiella", "Enterobacteriaceae", "Enterobacterales", "Gammaproteobacteria"],
    "Escherichia coli": ["Escherichia", "Enterobacteriaceae", "Enterobacterales", "Gammaproteobacteria"],
    "Pseudomonas aeruginosa": ["Pseudomonas", "Pseudomonadaceae", "Gammaproteobacteria"]
}

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

# --- CLINICAL MICROBIOLOGY CATEGORIZER ---
def categorize_pathogen(species_name):
    """Assigns an organism to a clinical reporting tier based on MCM standards."""
    name_lower = species_name.lower()
    
    known_pathogens = [
        "staphylococcus aureus", "klebsiella pneumoniae", "escherichia coli", 
        "pseudomonas aeruginosa", "vibrio cholerae", "streptococcus pyogenes", 
        "listeria monocytogenes", "salmonella", "shigella", "bacillus anthracis",
        "neisseria gonorrhoeae", "neisseria meningitidis", "legionella pneumophila",
        "campylobacter jejuni", "clostridioides difficile", "mycobacterium tuberculosis",
        "yersinia pestis", "yersinia enterocolitica", "haemophilus influenzae",
        "streptococcus pneumoniae", "enterobacter cloacae", "aeromonas hydrophila",
        "bacteroides fragilis"
    ]
    
    opportunistic = [
        "enterococcus faecalis", "enterococcus faecium", "acinetobacter baumannii",
        "staphylococcus epidermidis", "staphylococcus haemolyticus", "staphylococcus hominis",
        "staphylococcus lugdunensis", "proteus mirabilis", "serratia marcescens", 
        "stenotrophomonas maltophilia", "candida", "pseudomonas putida", "pseudomonas fluorescens",
        "citrobacter freundii", "morganella morganii", "providencia", "klebsiella oxytoca",
        "acinetobacter lwoffii", "burkholderia cepacia", "aeromonas caviae"
    ]
    
    commensal = [
        "lactobacillus", "bifidobacterium", "bacillus subtilis", "micrococcus",
        "cutibacterium", "corynebacterium", "veillonella", "rothia", "streptococcus salivarius",
        "streptococcus mitis", "streptococcus oralis", "streptococcus sanguinis",
        "actinomyces", "aerococcus", "arachnia", "bacteroides vulgatus", "bacteroides ovatus"
    ]
    
    for kp in known_pathogens:
        if kp in name_lower: return "Known Pathogens"
    for op in opportunistic:
        if op in name_lower: return "Opportunistic Pathogens"
    for cp in commensal:
        if cp in name_lower: return "Commensal / Environmental Microbes"
        
    return "Microbes with Pathogenic Potential"


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
            if target_bug == "Escherichia coli" and antibiotic == "Piperacillin" and marker.lower() == "blaec":
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

def generate_html_report(barcode, timestamp_label, all_detections, amr_results, out_dir):
    date_str = datetime.now().strftime("%b-%d-%Y %H:%M")
    report_name = f"PANACIA_Report_{barcode}_{timestamp_label}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    
    # Check for "Forced" to prevent slash issues in filenames while keeping UI clean
    display_time = "N/A" if timestamp_label == "Forced" else timestamp_label

    icon_path = os.path.join(PROJECT_ROOT, "icon_panacia.png")
    img_tag = ""
    if os.path.exists(icon_path):
        with open(icon_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
        img_tag = f'<img src="data:image/png;base64,{encoded_string}" style="height: 55px; margin-right: 15px;" alt="PANACIA Logo">'

    # --- BUILD TAXONOMY CARDS BY CATEGORY ---
    category_order = ["Known Pathogens", "Opportunistic Pathogens", "Microbes with Pathogenic Potential", "Commensal / Environmental Microbes"]
    category_colors = {
        "Known Pathogens": {"bg": "#fdeaea", "border": "#fa5c5c", "text": "#c92a2a"},
        "Opportunistic Pathogens": {"bg": "#fdf3e6", "border": "#f5a623", "text": "#b07005"},
        "Microbes with Pathogenic Potential": {"bg": "#f1f3f5", "border": "#adb5bd", "text": "#495057"},
        "Commensal / Environmental Microbes": {"bg": "#ebfbee", "border": "#40c057", "text": "#2b8a3e"}
    }
    
    pathogen_sections_html = ""
    for category in category_order:
        bugs_in_cat = [b for b in all_detections if b['category'] == category]
        if not bugs_in_cat:
            continue
            
        colors = category_colors[category]
        rows_html = ""
        for bug in bugs_in_cat:
            rows_html += f"""
            <tr>
                <td style="font-weight: 600;"><em>{bug['name']}</em></td>
                <td style="text-align: right;">{bug['reads']:,}</td>
                <td style="text-align: right; font-weight: bold;">{bug['abundance']:.2f}%</td>
            </tr>
            """
            
        pathogen_sections_html += f"""
        <div class="cat-card" style="background-color: {colors['bg']}; border-left: 5px solid {colors['border']};">
            <div class="cat-header" style="color: {colors['text']};">{category}</div>
            <table class="clinical-table">
                <thead>
                    <tr>
                        <th>Microorganism Name</th>
                        <th style="text-align: right;">Read Counts</th>
                        <th style="text-align: right;">Relative Abundance</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """
        
    if not pathogen_sections_html:
        pathogen_sections_html = "<div style='padding: 20px; color: #666; font-style: italic;'>No organisms detected above clinical thresholds.</div>"

    # --- ANTIBIOGRAM HTML ---
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
                        td_cols += "<td style='color: #555;'>S</td>"
                
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
                
        if amr_tables_content:
            amr_html = f"""
            <div class="section-title" style="margin-top: 40px;">TARGETED ANTIBIOGRAM</div>
            {amr_tables_content}
            """

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PANACIA Report | {barcode}</title>
        <style>
            body {{ font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; margin: 0; padding: 40px; color: #333; background-color: #fcfdfd; }}
            
            /* Increased max-width from 1000px to 1200px to fit antibiograms */
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-radius: 8px; }}
            
            .header-box {{ border-bottom: 3px solid #0e7480; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
            .title-area {{ display: flex; align-items: center; }}
            .header-box h1 {{ margin: 0; color: #0e7480; font-size: 28px; letter-spacing: 1px; line-height: 1.1; }}
            .meta-info {{ width: 100%; display: flex; justify-content: space-between; background: #f8f9fa; padding: 15px 20px; border-radius: 6px; margin-bottom: 35px; font-size: 14px; box-sizing: border-box; border: 1px solid #e9ecef; }}
            .section-title {{ font-size: 16px; font-weight: bold; background: #e9ecef; padding: 10px 15px; margin-top: 30px; margin-bottom: 20px; border-radius: 4px; color: #495057; text-transform: uppercase; letter-spacing: 0.5px; }}
            
            /* Pastel Card Styling */
            .cat-card {{ padding: 20px; margin-bottom: 20px; border-radius: 6px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }}
            .cat-header {{ font-size: 16px; font-weight: bold; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.5px; }}
            
            /* Table Styling */
            .clinical-table {{ width: 100%; border-collapse: collapse; font-size: 14px; background: rgba(255,255,255,0.6); }}
            .clinical-table th, .clinical-table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(0,0,0,0.08); text-align: left; }}
            .clinical-table th {{ text-transform: uppercase; font-size: 12px; color: #666; font-weight: 600; border-bottom: 2px solid rgba(0,0,0,0.1); }}
            .clinical-table tr:last-child td {{ border-bottom: none; }}
            
            /* Adjusted Matrix Table for tighter fit */
            .matrix-table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 20px; table-layout: fixed; }}
            .matrix-table th, .matrix-table td {{ text-align: center; border: 1px solid #ddd; padding: 8px 6px; word-wrap: break-word; }}
            .matrix-table th {{ background-color: #fafafa; color: #555; text-transform: uppercase; font-size: 11px; }}
            
            .footer {{ margin-top: 50px; font-size: 11px; color: #777; text-align: justify; border-top: 1px solid #ddd; padding-top: 15px; line-height: 1.5; }}
            .footer p {{ margin-top: 0; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-box">
                <div class="title-area">
                    {img_tag}
                    <div>
                        <h1>PANACIA TEST REPORT</h1>
                        <div style="margin-top: 5px; font-size: 14px; color: #666;">COMPREHENSIVE METAGENOMIC PROFILE</div>
                    </div>
                </div>
                <div style="text-align: right; font-weight: bold; color: #555; font-size: 14px;">
                    Report Time: {display_time}
                </div>
            </div>

            <div class="meta-info">
                <div><strong>Specimen ID:</strong> {barcode}</div>
                <div><strong>Report Generated:</strong> {date_str}</div>
                <div><strong>Specimen Type:</strong> BD BACTEC Blood Culture</div>
            </div>

            <div class="section-title">MICROBIAL DNA DETECTED</div>
            {pathogen_sections_html}

            {amr_html}

            <div class="footer">
                <p><strong>TEST DESCRIPTION & LIMITATIONS</strong><br>
                This comprehensive metagenomic profile identifies the presence and relative abundance of microbial species using Next-Generation Sequencing (NGS). 
                Organisms are categorized based on clinical guidelines. Detection requires absolute distinct minimizer complexities (&gt;{MIN_DISTINCT_MINIMIZERS}) 
                to eliminate false positives. The Targeted Antibiogram specifically screens for genotypic resistance markers in high-risk priority pathogens only. 
                A result of 'R' indicates genotypic detection of resistance; a result of 'S' implies the associated severe genotypic markers were absent, but does not guarantee phenotypic susceptibility due to intrinsic mechanisms or undetected novel mutations. 
                This test has not been cleared or approved by the FDA. Clinical correlation is required.</p>
                
                <p>Based on a review of Carroll KC, Pfaller MA. 2019. Manual of Clinical Microbiology, 12th Edition. ASM Press, Washington, DC and Bennett JE, Dolin R, Blaser MJ. 2019. Mandell, Douglas, and Bennett's Principles and Practice of Infectious Diseases, 9th Edition. Elsevier, Philadelphia, PA.</p>
            </div>
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
        
        all_detections = []
        detected_targets = set()
        
        # Parse all detections and check for priority AMR targets
        for _, row in valid_hits.iterrows():
            name = str(row['name']).strip()
            cat = categorize_pathogen(name)
            
            all_detections.append({
                "name": name,
                "reads": row['cumulative_bracken_reads'],
                "abundance": row['true_relative_abundance'],
                "category": cat
            })
            
            # Map detected bug back to exact TARGET_SPECIES string if applicable
            for target in TARGET_SPECIES:
                if target.lower() in name.lower():
                    detected_targets.add(target)

        # 2. Extract AMR Data for Targets (Including Plasmid/Mobile Elements AND Lineage Roll-Down)
        amr_results = {}
        if os.path.exists(json_path) and detected_targets:
            with open(json_path, 'r') as f:
                amr_data = json.load(f)
                
            for bug in detected_targets:
                bug_amr = {}
                allowed_parents = LINEAGE_MAP.get(bug, [])
                
                for json_org, drug_classes in amr_data.items():
                    is_match = False
                    
                    # Direct match or floating plasmid bin
                    if bug.lower() in json_org.lower() or json_org == "Unassigned / Mobile Elements":
                        is_match = True
                    else:
                        # Clinical Roll-Down match
                        for parent in allowed_parents:
                            if parent.lower() in json_org.lower():
                                is_match = True
                                break
                                
                    if is_match:
                        for dc, genes in drug_classes.items():
                            if dc not in bug_amr:
                                bug_amr[dc] = []
                            bug_amr[dc].extend(genes)
                            
                amr_results[bug] = check_amr_resistance(bug, bug_amr)

        # 3. Generate HTML
        generate_html_report(barcode, time_label, all_detections, amr_results, reports_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate targeted clinical reports.")
    parser.add_argument("agg_dir", help="Path to aggregated_results directory")
    parser.add_argument("--force", action="store_true", help="Force generation ignoring the 6-hour timer")
    args = parser.parse_args()
    
    process_batch(args.agg_dir, args.force)