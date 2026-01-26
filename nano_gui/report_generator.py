import os
import time
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from PyQt6.QtCore import QThread, pyqtSignal

class ReportGenerator(QThread):
    log_message = pyqtSignal(str)

    def __init__(self, output_dir, run_name="MetaRT Analysis"):
        super().__init__()
        self.output_dir = os.path.abspath(output_dir)
        self.agg_dir = os.path.join(self.output_dir, "aggregated_results")
        self.report_path = os.path.join(self.agg_dir, "dashboard.html")
        self.run_name = run_name
        self.active = True

    def run(self):
        self.log_message.emit(f"Report: Monitoring {self.agg_dir}")
        while self.active:
            try:
                self.generate_report()
            except Exception as e:
                self.log_message.emit(f"Report Error: {str(e)}")
            
            # Sleep 30 seconds
            for _ in range(30):
                if not self.active: return
                time.sleep(1)

    def stop(self):
        self.active = False
        self.wait()

    def _load_csv(self, filename):
        path = os.path.join(self.agg_dir, filename)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                return df if not df.empty else None
            except:
                return None
        return None

    def generate_report(self):
        # 1. Load Data with CORRECT filenames matching the GUI widgets
        df_acc = self._load_csv("cumulative_species_data.csv")  # Fixed filename
        df_rare = self._load_csv("rarefaction_data.csv")
        df_abund = self._load_csv("abundance_data.csv")

        # 2. Prepare Figures
        div_acc = self._create_accumulation_chart(df_acc)
        div_rare = self._create_rarefaction_chart(df_rare)
        
        # Create BOTH Absolute and Relative charts
        div_abs_abund = self._create_abundance_chart(df_abund, mode='absolute')
        div_rel_abund = self._create_abundance_chart(df_abund, mode='relative')
        
        div_sunburst = self._create_sunburst_chart(df_abund)
        
        # 3. Calculate KPIs (Simple totals)
        total_reads_count = 0
        if df_acc is not None and not df_acc.empty:
            # Sum the maximum cumulative reads for each barcode/species combo to get a rough total
            # (Approximation depends on how cumulative_species_data is structured, assuming it tracks species counts)
            # A safer KPI for "Total Reads" is usually in a separate run_stats file, but we can infer:
             total_reads_count = df_acc.groupby(['barcode', 'name'])['cumulative_reads'].max().sum()
        
        total_species_count = 0
        if df_rare is not None:
            total_species_count = df_rare['unique_species_count'].max()

        # 4. Generate HTML (Marti-Style Layout)
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="30">
            <title>{self.run_name} | Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    background-color: #f0f2f5;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .navbar {{
                    background-color: #3c5457; /* Marti/Chromologic Teal */
                    color: white;
                    padding: 1rem 2rem;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    display: flex; justify-content: space-between; align-items: center;
                }}
                .navbar h1 {{ margin: 0; font-size: 1.4rem; font-weight: 600; letter-spacing: 0.5px; }}
                
                .container {{
                    max-width: 1600px; margin: 2rem auto; padding: 0 1rem;
                    display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;
                }}
                
                .card {{
                    background: white; border-radius: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    padding: 1.5rem; border: 1px solid #e1e4e8;
                }}
                .card.full-width {{ grid-column: span 2; }}
                .card h2 {{ 
                    font-size: 1.1rem; color: #555; margin-top: 0; margin-bottom: 1rem; 
                    border-bottom: 2px solid #f4f4f4; padding-bottom: 10px;
                }}

                /* KPI Cards */
                .kpi-row {{ grid-column: span 2; display: flex; gap: 1.5rem; margin-bottom: 0.5rem; }}
                .kpi-card {{
                    flex: 1; background: white; padding: 1.5rem; border-radius: 8px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-left: 5px solid #007AFF;
                }}
                .kpi-value {{ font-size: 2.2rem; font-weight: bold; color: #3c5457; }}
                .kpi-label {{ color: #888; font-size: 0.85rem; text-transform: uppercase; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="navbar">
                <h1>{self.run_name} <span style="font-weight:300; opacity:0.8;">| Real-Time Report</span></h1>
                <span style="font-size: 0.85rem; background: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 4px;">Live Auto-Refresh</span>
            </div>

            <div class="container">
                <div class="kpi-row">
                    <div class="kpi-card">
                        <div class="kpi-label">Total Reads Classified</div>
                        <div class="kpi-value">{total_reads_count:,.0f}</div>
                    </div>
                    <div class="kpi-card" style="border-left-color: #34C759;">
                        <div class="kpi-label">Unique Species Detected</div>
                        <div class="kpi-value">{total_species_count:,.0f}</div>
                    </div>
                </div>

                <div class="card">
                    <h2>Reads Over Time (Accumulation)</h2>
                    {div_acc}
                </div>
                <div class="card">
                    <h2>Species Discovery (Rarefaction)</h2>
                    {div_rare}
                </div>

                <div class="card full-width">
                    <h2>Relative Abundance (%)</h2>
                    {div_rel_abund}
                </div>

                <div class="card full-width">
                    <h2>Absolute Abundance (Read Counts)</h2>
                    {div_abs_abund}
                </div>

                 <div class="card full-width">
                    <h2>Taxonomy Overview</h2>
                    {div_sunburst}
                </div>
            </div>
        </body>
        </html>
        """

        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(html_template)
            
        self.log_message.emit(f"Report: Updated dashboard.html")

    # --- Chart Generators ---

    def _create_accumulation_chart(self, df):
        if df is None: return "<div>Waiting for data (cumulative_species_data.csv)...</div>"
        
        # The GUI parses 'cumulative_species_data.csv'. 
        # Columns: name, tax_id, barcode, timestamp, cumulative_reads
        # To match the "Total Reads per Barcode" view:
        try:
            # 1. Group by Barcode + Timestamp -> Sum of reads across all species
            df_agg = df.groupby(['barcode', 'timestamp'])['cumulative_reads'].sum().reset_index()
            
            fig = px.line(df_agg, x='timestamp', y='cumulative_reads', color='barcode',
                          template="plotly_white")
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350)
            return fig.to_html(full_html=False, include_plotlyjs=False)
        except Exception as e:
            return f"<div>Error plotting accumulation: {e}</div>"

    def _create_rarefaction_chart(self, df):
        if df is None: return "<div>Waiting for data (rarefaction_data.csv)...</div>"
        
        try:
            fig = px.line(df, x='timestamp', y='unique_species_count', color='barcode',
                          template="plotly_white")
            fig.update_traces(line=dict(dash='dot'))
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350)
            return fig.to_html(full_html=False, include_plotlyjs=False)
        except:
            return "<div>Error plotting rarefaction</div>"

    def _create_abundance_chart(self, df, mode='relative'):
        """
        Generates either Absolute or Relative abundance bar chart.
        Ensures correct sorting and normalization.
        """
        if df is None: return "<div>Waiting for data...</div>"

        # 1. Filter Top 20 Species by Total Count (to avoid overcrowding)
        top_species = df.groupby('name')['absolute_abundance'].sum().nlargest(20).index
        filtered = df[df['name'].isin(top_species)].copy()

        # 2. Sort Barcodes Alphabetically
        filtered.sort_values('barcode', inplace=True)

        if mode == 'absolute':
            y_col = 'absolute_abundance'
            title_y = "Read Count"
        else:
            # 3. RELATIVE MODE FIX: Re-calculate percentages strictly
            # Group by barcode to get total reads per barcode
            barcode_totals = filtered.groupby('barcode')['absolute_abundance'].transform('sum')
            # Calculate % for the plot
            filtered['calculated_percent'] = (filtered['absolute_abundance'] / barcode_totals) * 100
            y_col = 'calculated_percent'
            title_y = "Relative Abundance (%)"

        fig = px.bar(filtered, x='barcode', y=y_col, color='name',
                     template="plotly_white", 
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), 
            height=450, 
            barmode='stack',
            xaxis={'categoryorder': 'category ascending'}, # Force A-Z order
            yaxis_title=title_y
        )
        return fig.to_html(full_html=False, include_plotlyjs=False)
        
    def _create_sunburst_chart(self, df):
        if df is None: return "<div>Waiting for data...</div>"
        
        # Simple species sunburst
        top_species = df.groupby('name')['absolute_abundance'].sum().nlargest(30).reset_index()
        
        fig = px.sunburst(top_species, path=['name'], values='absolute_abundance',
                          color_discrete_sequence=px.colors.qualitative.Pastel)
        
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450)
        return fig.to_html(full_html=False, include_plotlyjs=False)