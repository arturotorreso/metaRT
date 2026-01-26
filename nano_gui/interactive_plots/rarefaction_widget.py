# nano_gui/interactive_plots/rarefaction_widget.py
import os
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from .interactive_plot_widget import InteractivePlotWidget

class DataLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)
    failed = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if not os.path.exists(self.file_path): return
            df = pd.read_csv(self.file_path)
            self.data_loaded.emit(df)
        except Exception as e:
            self.failed.emit(str(e))

class RarefactionPlot(InteractivePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_widget.setTitle("Species Rarefaction Curve", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Unique Species Count', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.plot_widget.setBackground('w')
        
        # --- PERFORMANCE OPTIMIZATION ---
        self.plot_widget.setDownsampling(mode='peak')
        self.plot_widget.setClipToView(True)
        pg.setConfigOptions(antialias=True)
        
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        
        self.legend = self.plot_widget.addLegend()
        self.curves = {} # Cache for curves
        self.loader = None 

    def update_data(self, data_file):
        if not os.path.exists(data_file): return
        if self.loader is not None and self.loader.isRunning(): return

        self.loader = DataLoader(data_file)
        self.loader.data_loaded.connect(self.on_data_loaded)
        self.loader.start()

    @pyqtSlot(pd.DataFrame)
    def on_data_loaded(self, df):
        try:
            if df.empty: return

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['barcode'] = df['barcode'].str.strip()
            
            unique_barcodes = df['barcode'].unique()
            
            for i, (barcode, group) in enumerate(df.groupby('barcode')):
                sorted_group = group.sort_values('timestamp')
                x_data = (sorted_group['timestamp'].astype('int64') / 10**9).to_numpy()
                y_data = sorted_group['unique_species_count'].to_numpy()
                
                # --- FAST UPDATE ---
                if barcode in self.curves:
                    self.curves[barcode].setData(x_data, y_data)
                else:
                    # Create new curve
                    pen = pg.mkPen(color=pg.intColor(i, hues=len(unique_barcodes)), width=2)
                    curve = self.plot_widget.plot(x_data, y_data, pen=pen, name=barcode)
                    self.curves[barcode] = curve
            
            # Note: We do NOT call clear(), so the legend stays valid.

        except Exception as e:
            print(f"Error updating rarefaction plot: {e}")