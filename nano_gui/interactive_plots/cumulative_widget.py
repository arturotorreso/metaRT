# nano_gui/interactive_plots/cumulative_widget.py
import os
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import QTabWidget, QWidget, QVBoxLayout
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot

class DataLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)
    failed = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if not os.path.exists(self.file_path):
                return
            # Optimize: Read only necessary columns if file is huge
            df = pd.read_csv(self.file_path)
            self.data_loaded.emit(df)
        except Exception as e:
            self.failed.emit(str(e))

class SingleBarcodePlot(QWidget):
    def __init__(self, barcode, parent=None):
        super().__init__(parent)
        self.barcode = barcode
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle(f"Cumulative Reads for {barcode}", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Cumulative Read Count', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.plot_widget.setLogMode(y=True)
        self.plot_widget.setBackground('w')
        
        # --- PERFORMANCE OPTIMIZATION ---
        # 1. Downsampling: Reduces rendering load for large datasets (>10k points)
        self.plot_widget.setDownsampling(mode='peak') 
        # 2. ClipToView: Don't render what isn't visible (when zoomed in)
        self.plot_widget.setClipToView(True)
        
        pg.setConfigOptions(antialias=True)
        
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        
        self.legend = self.plot_widget.addLegend()
        self.curves = {} # Store references to plot items
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

    def update_plot_data(self, barcode_df):
        try:
            if barcode_df.empty: return

            barcode_df['timestamp'] = pd.to_datetime(barcode_df['timestamp'])
            latest_timestamp = barcode_df['timestamp'].max()
            latest_data = barcode_df[barcode_df['timestamp'] == latest_timestamp]
            
            # Sort by top 10 species
            sorted_latest_data = latest_data.sort_values('cumulative_reads', ascending=False)
            top_species_ordered = sorted_latest_data.nlargest(10, 'cumulative_reads')['name'].tolist()
            
            plot_df = barcode_df[barcode_df['name'].isin(top_species_ordered)]
            if plot_df.empty: return

            current_species_in_plot = set()

            for i, species_name in enumerate(top_species_ordered):
                group = plot_df[plot_df['name'] == species_name]
                if group.empty: continue

                sorted_group = group.sort_values('timestamp')
                x_data = (sorted_group['timestamp'].astype('int64') / 10**9).to_numpy()
                y_data = sorted_group['cumulative_reads'].to_numpy()
                
                current_species_in_plot.add(species_name)

                # --- PERFORMANCE FIX: RECYCLE CURVES ---
                if species_name in self.curves:
                    # Instant update, no memory reallocation
                    self.curves[species_name].setData(x_data, y_data)
                    # Ensure it is visible if it was hidden
                    if not self.curves[species_name].isVisible():
                        self.curves[species_name].show()
                else:
                    # Expensive creation (happens only once per species)
                    color = pg.intColor(i, hues=10, values=1, maxValue=255)
                    pen = pg.mkPen(color=color, width=2)
                    curve = self.plot_widget.plot(x_data, y_data, pen=pen, name=species_name)
                    self.curves[species_name] = curve

            # Hide species that dropped out of top 10 (don't delete, just hide)
            for name, curve in self.curves.items():
                if name not in current_species_in_plot:
                    curve.hide()

        except Exception as e:
            print(f"Error updating plot: {e}")

class CumulativePlot(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.barcode_plots = {} 
        self.loader = None 

    def update_data(self, data_file):
        if not os.path.exists(data_file): return
        if self.loader is not None and self.loader.isRunning(): return

        self.loader = DataLoader(data_file)
        self.loader.data_loaded.connect(self.on_data_loaded)
        self.loader.start()

    @pyqtSlot(pd.DataFrame)
    def on_data_loaded(self, df):
        if df.empty: return
        try:
            df['barcode'] = df['barcode'].str.strip()
            all_barcodes = df['barcode'].unique()

            for barcode in all_barcodes:
                if barcode not in self.barcode_plots:
                    plot_widget = SingleBarcodePlot(barcode)
                    self.barcode_plots[barcode] = plot_widget
                    self.addTab(plot_widget, barcode)

            # Update ONLY the currently visible tab to save resources
            # Or iterate all if you want background tabs to be up-to-date
            current_idx = self.currentIndex()
            if current_idx != -1:
                current_barcode = self.tabText(current_idx)
                if current_barcode in self.barcode_plots:
                    barcode_df = df[df['barcode'] == current_barcode].copy()
                    self.barcode_plots[current_barcode].update_plot_data(barcode_df)
                    
        except Exception as e:
            print(f"Error processing data: {e}") 