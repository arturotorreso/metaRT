# nano_gui/interactive_plots/cumulative_widget.py
import os
import pandas as pd
import pyqtgraph as pg
from .interactive_plot_widget import InteractivePlotWidget

class CumulativePlot(InteractivePlotWidget):
    def __init__(self, barcode, parent=None):
        super().__init__(parent)
        self.barcode = barcode
        self.plot_widget.setTitle(f"Cumulative Reads for {barcode}", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Cumulative Read Count', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.plot_widget.setLogMode(y=True)
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        self.legend = None # Initialize legend attribute

    def update_data(self, data_file):
        if not os.path.exists(data_file):
            return

        try:
            self.plot_widget.clear()

            # **FIX 1**: Forcefully remove and recreate the legend on each update
            if self.legend:
                self.plot_widget.removeItem(self.legend)
            self.legend = self.plot_widget.addLegend()

            df = pd.read_csv(data_file)
            if df.empty:
                return

            df['barcode'] = df['barcode'].str.strip()
            df['name'] = df['name'].str.strip()

            barcode_df = df[df['barcode'] == self.barcode].copy()
            if barcode_df.empty:
                return

            barcode_df['timestamp'] = pd.to_datetime(barcode_df['timestamp'])

            latest_timestamp = barcode_df['timestamp'].max()
            latest_data = barcode_df[barcode_df['timestamp'] == latest_timestamp]
            top_species = latest_data.nlargest(10, 'cumulative_reads')['name'].tolist()
            
            plot_df = barcode_df[barcode_df['name'].isin(top_species)]
            
            if plot_df.empty:
                return

            unique_species = plot_df['name'].unique()
            for i, (species_name, group) in enumerate(plot_df.groupby('name')):
                sorted_group = group.sort_values('timestamp')
                pen = pg.mkPen(color=pg.intColor(i, hues=len(unique_species)), width=2)
                
                # **FIX 2**: Convert data to NumPy arrays before plotting
                x_data = (sorted_group['timestamp'].astype(int) / 10**9).to_numpy()
                y_data = sorted_group['cumulative_reads'].to_numpy()
                
                self.plot_widget.plot(x_data, y_data, pen=pen, name=species_name)

        except Exception as e:
            print(f"Error updating cumulative plot for {self.barcode}: {e}")