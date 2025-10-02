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

    def update_data(self, data_file):
        if not os.path.exists(data_file):
            return

        try:
            df = pd.read_csv(data_file)
            if df.empty:
                return

            barcode_df = df[df['barcode'] == self.barcode].copy()
            if barcode_df.empty:
                return

            top_species = barcode_df.groupby('name')['cumulative_reads'].max().nlargest(10).index
            plot_df = barcode_df[barcode_df['name'].isin(top_species)]
            
            plot_df['timestamp'] = pd.to_datetime(plot_df['timestamp'])
            plot_df['time_seconds'] = (plot_df['timestamp'] - plot_df['timestamp'].min()).dt.total_seconds()
            
            self.plot_widget.clear()
            self.legend.clear()

            for i, species in enumerate(plot_df['name'].unique()):
                species_df = plot_df[plot_df['name'] == species]
                pen = pg.mkPen(color=pg.intColor(i, hues=len(plot_df['name'].unique())), width=2)
                plot_item = self.plot_widget.plot(
                    species_df['time_seconds'], 
                    species_df['cumulative_reads'], 
                    pen=pen, 
                    name=species
                )
                self.legend.addItem(plot_item, species)

        except Exception as e:
            print(f"Error updating cumulative plot for {self.barcode}: {e}")