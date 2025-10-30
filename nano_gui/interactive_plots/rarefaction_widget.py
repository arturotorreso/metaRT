# nano_gui/interactive_plots/rarefaction_widget.py
import os
import pandas as pd
import pyqtgraph as pg
from .interactive_plot_widget import InteractivePlotWidget

class RarefactionPlot(InteractivePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_widget.setTitle("Species Rarefaction Curve", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Unique Species Count', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        self.legend = None # Initialize legend attribute

    def update_data(self, data_file):
        if not os.path.exists(data_file):
            return

        try:
            self.plot_widget.clear()

            # Forcefully remove and recreate the legend on each update
            if self.legend:
                self.plot_widget.removeItem(self.legend)
            self.legend = self.plot_widget.addLegend()

            df = pd.read_csv(data_file)
            if df.empty:
                return

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['barcode'] = df['barcode'].str.strip()
            
            unique_barcodes = df['barcode'].unique()
            for i, (barcode, group) in enumerate(df.groupby('barcode')):
                sorted_group = group.sort_values('timestamp')
                pen = pg.mkPen(color=pg.intColor(i, hues=len(unique_barcodes)), width=2)
                
                # Convert data to NumPy arrays before plotting
                x_data = (sorted_group['timestamp'].astype(int) / 10**9).to_numpy()
                y_data = sorted_group['unique_species_count'].to_numpy()
                
                self.plot_widget.plot(x_data, y_data, pen=pen, name=barcode)

        except Exception as e:
            print(f"Error updating rarefaction plot: {e}")