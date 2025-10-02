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
        self.plot_widget.getAxis("bottom").setTickSpacing(100, 1)

    def update_data(self, data_file):
        if not os.path.exists(data_file):
            return

        try:
            df = pd.read_csv(data_file)
            if df.empty:
                return

            self.plot_widget.clear()
            self.legend.clear()

            # Convert timestamp to a numerical value for plotting
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['time_seconds'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds()

            for i, barcode in enumerate(df['barcode'].unique()):
                barcode_df = df[df['barcode'] == barcode]
                pen = pg.mkPen(color=pg.intColor(i, hues=len(df['barcode'].unique())), width=2)
                
                # Create a plot item with a name for the legend
                plot_item = self.plot_widget.plot(
                    barcode_df['time_seconds'], 
                    barcode_df['unique_species_count'], 
                    pen=pen, 
                    name=barcode
                )
                self.legend.addItem(plot_item, barcode)

        except Exception as e:
            print(f"Error updating rarefaction plot: {e}")