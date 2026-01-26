# nano_gui/reporting.py
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from PyQt6.QtCore import QThread, pyqtSignal

class ReportGenerator(QThread):
    """
    Background thread that generates a standalone HTML dashboard 
    for the customer. It runs periodically to avoid slowing down the GUI.
    """
    finished = pyqtSignal(str) # Emits path to generated report

    def __init__(self, output_dir, run_name="Metagenomic Run"):
        super().__init__()
        self.output_dir = output_dir
        self.run_name = run_name
        self.agg_dir = os.path.join(output_dir, "aggregated_results")
        self.report_path = os.path.join(self.agg_dir, "customer_report.html")

    def run(self):
        try:
            # 1. Load Data
            df_acc = self._load_csv("accumulation.csv")
            df_rare = self._load_csv("rarefaction_data.csv")
            df_abund = self._load_csv("abundance_data.csv")

            if df_acc is None and df_rare is None:
                return

            # 2. Create Plotly Figures
            fig = make_subplots(
                rows=2, cols=2,
                specs=[[{"type": "xy"}, {"type": "xy"}],
                       [{"type": "domain", "colspan": 2}, None]],
                subplot_titles=("Reads Over Time", "Species Discovery (Rarefaction)", "Top Pathogens")
            )

            # A. Accumulation Line
            if df_acc is not None:
                for barcode in df_acc['barcode'].unique():
                    sub = df_acc[df_acc['barcode'] == barcode]
                    fig.add_trace(go.Scatter(x=sub['timestamp'], y=sub['cumulative_reads'], 
                                             mode='lines', name=f"{barcode} Reads"), row=1, col=1)

            # B. Rarefaction Line
            if df_rare is not None:
                for barcode in df_rare['barcode'].unique():
                    sub = df_rare[df_rare['barcode'] == barcode]
                    fig.add_trace(go.Scatter(x=sub['timestamp'], y=sub['unique_species_count'], 
                                             mode='lines', name=f"{barcode} Species"), row=1, col=2)
            
            # C. Sunburst or Pie for Abundance (Simplified for report)
            if df_abund is not None:
                # Aggregate top species across all barcodes for a summary view
                top_species = df_abund.groupby('name')['absolute_abundance'].sum().nlargest(10).reset_index()
                fig.add_trace(go.Pie(labels=top_species['name'], values=top_species['absolute_abundance']), row=2, col=1)

            # 3. Aesthetics
            fig.update_layout(
                title_text=f"Real-Time Analysis: {self.run_name}",
                template="plotly_white",
                height=800,
                showlegend=True
            )

            # 4. Generate HTML with Auto-Refresh
            html_content = fig.to_html(include_plotlyjs='cdn', full_html=True)
            
            # Inject Refresh Header (Auto-reload every 300 seconds / 5 mins)
            refresh_tag = '<meta http-equiv="refresh" content="300">'
            # Inject Custom CSS for Marti-like Header
            custom_style = """
            <style>
                body { font-family: -apple-system, sans-serif; background: #f9f9f9; padding: 20px; }
                .main-svg { border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            </style>
            """
            
            html_content = html_content.replace('<head>', f'<head>{refresh_tag}{custom_style}')
            
            with open(self.report_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            self.finished.emit(self.report_path)

        except Exception as e:
            print(f"Report generation failed: {e}")

    def _load_csv(self, filename):
        path = os.path.join(self.agg_dir, filename)
        if os.path.exists(path):
            try:
                return pd.read_csv(path)
            except:
                return None
        return None