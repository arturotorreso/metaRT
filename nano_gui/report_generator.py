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
        # Ensure we look in the correct subdirectory where result_aggregator puts files
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
                # Log error but keep running to retry next cycle
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
        # 1. Load Data
        df_acc = self._load_csv("cumulative_species_data.csv")
        df_rare = self._load_csv("rarefaction_data.csv")
        df_abund = self._load_csv("abundance_data.csv")

        # 2. Prepare Figures
        acc_tabs_html = self._create_accumulation_tabs(df_acc)
        div_rare = self._create_rarefaction_chart(df_rare)
        
        # Create BOTH Absolute and Relative charts
        div_abs_abund = self._create_abundance_chart(df_abund, mode='absolute')
        div_rel_abund = self._create_abundance_chart(df_abund, mode='relative')
        
        div_overview = self._create_overview_pie(df_abund)
        
        # 3. Calculate KPIs (Simple totals)
        total_reads_count = 0
        if df_acc is not None and not df_acc.empty:
            # Sum the maximum cumulative reads for each barcode/species combo
            total_reads_count = df_acc.groupby(['barcode', 'name'])['cumulative_reads'].max().sum()
        
        total_species_count = 0
        if df_rare is not None and not df_rare.empty:
            total_species_count = df_rare['unique_species_count'].max()

        # 4. Generate HTML
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
                    background-color: #3c5457;
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

                /* Custom Tabs */
                .tab {{ overflow: hidden; border-bottom: 1px solid #ccc; margin-bottom: 10px; }}
                .tab button {{
                    background-color: inherit; float: left; border: none; outline: none;
                    cursor: pointer; padding: 10px 16px; transition: 0.3s; font-size: 14px;
                    border-bottom: 3px solid transparent; color: #666; font-weight: bold;
                }}
                .tab button:hover {{ color: #3c5457; }}
                .tab button.active {{ border-bottom: 3px solid #3c5457; color: #3c5457; }}
                .tabcontent {{ display: none; padding: 6px 0; }}
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

                <div class="card full-width">
                    <h2>Species Accumulation per Barcode</h2>
                    {acc_tabs_html}
                </div>

                <div class="card full-width">
                    <h2>Relative Abundance (%)</h2>
                    {div_rel_abund}
                </div>

                <div class="card full-width">
                    <h2>Absolute Abundance (Read Counts)</h2>
                    {div_abs_abund}
                </div>
                
                 <div class="card">
                    <h2>Species Discovery (Rarefaction)</h2>
                    {div_rare}
                </div>

                 <div class="card">
                    <h2>Global Taxonomy Overview</h2>
                    {div_overview}
                </div>
            </div>
            
            <script>
                function openTab(evt, tabId) {{
                    var i, tabcontent, tablinks;
                    tabcontent = document.getElementsByClassName("tabcontent");
                    for (i = 0; i < tabcontent.length; i++) {{
                        tabcontent[i].style.display = "none";
                    }}
                    tablinks = document.getElementsByClassName("tablinks");
                    for (i = 0; i < tablinks.length; i++) {{
                        tablinks[i].className = tablinks[i].className.replace(" active", "");
                    }}
                    document.getElementById(tabId).style.display = "block";
                    evt.currentTarget.className += " active";
                }}
                
                // Click the first tab by default to show it on load
                document.addEventListener("DOMContentLoaded", function() {{
                    var firstTab = document.querySelector('.tablinks');
                    if(firstTab) firstTab.click();
                }});
            </script>
        </body>
        </html>
        """

        # Write the file atomically if possible, or just overwrite
        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(html_template)
            
        self.log_message.emit(f"Report: Updated dashboard.html")

    # --- Chart Generators ---

    def _create_accumulation_tabs(self, df):
        if df is None or df.empty: return "<div>Waiting for data (cumulative_species_data.csv)...</div>"
        
        try:
            # 1. Clean and sort data
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values(by=['barcode', 'timestamp'])
            barcodes = sorted(df['barcode'].unique())
            
            # 2. Build HTML Tabs structure
            tabs_buttons = '<div class="tab">'
            tabs_content = ''
            
            for bc in barcodes:
                safe_id = f"tab_{bc.replace('-', '_')}"
                tabs_buttons += f'<button class="tablinks" onclick="openTab(event, \'{safe_id}\')">{bc}</button>'
                
                sub_df = df[df['barcode'] == bc].copy()
                
                # Filter Top 10 Species to prevent visual clutter
                top_sp = sub_df.groupby('name')['cumulative_reads'].max().nlargest(10).index
                sub_df = sub_df[sub_df['name'].isin(top_sp)]
                
                fig = px.line(sub_df, x='timestamp', y='cumulative_reads', color='name',
                              template="plotly_white", markers=True)
                              
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=450,
                                  xaxis_title="Time", yaxis_title="Cumulative Reads",
                                  legend_title_text="Species")
                
                div = fig.to_html(full_html=False, include_plotlyjs=False)
                tabs_content += f'<div id="{safe_id}" class="tabcontent">{div}</div>'

            tabs_buttons += '</div>'
            return tabs_buttons + tabs_content

        except Exception as e:
            return f"<div>Error plotting accumulation: {e}</div>"

    def _create_rarefaction_chart(self, df):
        if df is None or df.empty: return "<div>Waiting for data (rarefaction_data.csv)...</div>"
        
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Drop duplicates and sort to prevent overlapping zig-zag lines
            df = df.drop_duplicates(subset=['barcode', 'timestamp'], keep='last').sort_values(by=['barcode', 'timestamp'])
            
            fig = px.line(df, x='timestamp', y='unique_species_count', color='barcode',
                          template="plotly_white", markers=True)
                          
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350,
                              xaxis_title="Time", yaxis_title="Unique Species Found")
                              
            return fig.to_html(full_html=False, include_plotlyjs=False)
        except Exception as e:
            return f"<div>Error plotting rarefaction: {e}</div>"

    def _create_abundance_chart(self, df, mode='relative'):
        """
        Generates either Absolute or Relative abundance bar chart.
        Ensures correct sorting and normalization.
        """
        if df is None or df.empty: return "<div>Waiting for data...</div>"
        try:
            # 1. Take ONLY the latest read count per species per barcode to prevent "stairs"
            df = df.groupby(['barcode', 'name'])['absolute_abundance'].max().reset_index()

            # 2. Calculate percentages properly
            if mode == 'relative':
                barcode_totals = df.groupby('barcode')['absolute_abundance'].transform('sum')
                df['calculated_percent'] = (df['absolute_abundance'] / barcode_totals) * 100
                y_col = 'calculated_percent'
                title_y = "Relative Abundance (%)"
            else:
                y_col = 'absolute_abundance'
                title_y = "Read Count"

            # 3. Filter Top Species globally for consistent legend colors
            top_species = df.groupby('name')['absolute_abundance'].sum().nlargest(20).index
            filtered = df[df['name'].isin(top_species)].copy()
            filtered.sort_values('barcode', inplace=True)

            fig = px.bar(filtered, x='barcode', y=y_col, color='name',
                         template="plotly_white", barmode='stack',
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), height=450, 
                xaxis={'categoryorder': 'category ascending'}, 
                xaxis_title="", yaxis_title=title_y, legend_title_text="Species"
            )
            return fig.to_html(full_html=False, include_plotlyjs=False)
        except Exception as e:
            return f"<div>Error plotting abundance: {e}</div>"
        
    def _create_overview_pie(self, df):
        if df is None or df.empty: return "<div>Waiting for data...</div>"
        try:
            # Get latest counts, then aggregate globally across all barcodes
            df = df.groupby(['barcode', 'name'])['absolute_abundance'].max().reset_index()
            top_species = df.groupby('name')['absolute_abundance'].sum().nlargest(15).reset_index()
            
            # Clean donut chart
            fig = px.pie(top_species, names='name', values='absolute_abundance',
                         color_discrete_sequence=px.colors.qualitative.Pastel, hole=0.4)
            
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350,
                              annotations=[dict(text='Top Species', x=0.5, y=0.5, font_size=14, showarrow=False)])
                              
            # Put text directly inside the pie slices, remove messy legend
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(showlegend=False)
            
            return fig.to_html(full_html=False, include_plotlyjs=False)
        except Exception as e:
            return f"<div>Error plotting overview: {e}</div>"