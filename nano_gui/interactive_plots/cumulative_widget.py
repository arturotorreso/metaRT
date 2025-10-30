# nano_gui/interactive_plots/cumulative_widget.py
import os
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import QTabWidget, QWidget, QVBoxLayout

class SingleBarcodePlot(QWidget):
    """A widget to display the cumulative plot for a single barcode."""
    def __init__(self, barcode, parent=None):
        super().__init__(parent)
        self.barcode = barcode
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle(f"Cumulative Reads for {barcode}", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Cumulative Read Count', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.plot_widget.setLogMode(y=True)
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        
        self.legend = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

    def update_plot_data(self, barcode_df):
        """Updates the plot with the provided DataFrame for this barcode."""
        try:
            self.plot_widget.clear()
            if self.legend:
                # Manually clear items from the legend to prevent duplicates
                self.legend.clear()
            else:
                # Create the legend only once
                self.legend = self.plot_widget.addLegend()

            if barcode_df.empty:
                return

            barcode_df['timestamp'] = pd.to_datetime(barcode_df['timestamp'])
            latest_timestamp = barcode_df['timestamp'].max()
            latest_data = barcode_df[barcode_df['timestamp'] == latest_timestamp]
            
            # Get top 10 species, ordered by abundance for the legend
            sorted_latest_data = latest_data.sort_values('cumulative_reads', ascending=False)
            top_species_ordered = sorted_latest_data.nlargest(10, 'cumulative_reads')['name'].tolist()
            
            plot_df = barcode_df[barcode_df['name'].isin(top_species_ordered)]
            if plot_df.empty: return

            # Plot the data in the determined order
            for i, species_name in enumerate(top_species_ordered):
                group = plot_df[plot_df['name'] == species_name]
                if group.empty: continue

                sorted_group = group.sort_values('timestamp')
                pen = pg.mkPen(color=pg.intColor(i, hues=len(top_species_ordered)), width=2)
                
                x_data = (sorted_group['timestamp'].astype(int) / 10**9).to_numpy()
                y_data = sorted_group['cumulative_reads'].to_numpy()
                
                # Add the plot and let the legend populate automatically
                self.plot_widget.plot(x_data, y_data, pen=pen, name=species_name)

            # Manually set up click handlers for each legend item after plotting
            self.setup_legend_interaction()

        except Exception as e:
            print(f"Error updating cumulative plot for {self.barcode}: {e}")

    def setup_legend_interaction(self):
        """Iterate through legend items and assign a click handler to each label."""
        if not self.legend:
            return
        # `self.legend.items` holds tuples of (sample, label)
        for sample, label in self.legend.items:
            # The `sample.item` attribute is the actual PlotDataItem (the curve)
            curve = sample.item
            # Use a lambda with default arguments to capture the current curve and label
            # for the handler. This is the standard way to solve the loop closure issue.
            label.mouseClickEvent = lambda event, c=curve, l=label: self.on_legend_item_clicked(c, l)
            
    def on_legend_item_clicked(self, curve, label):
        """Handles a click on a legend's label item."""
        # Toggle the visibility of the curve
        is_visible = not curve.isVisible()
        curve.setVisible(is_visible)
        
        # Update the label's text color to reflect the state
        name = curve.opts['name']
        if is_visible:
            label.setText(name, color='k') # Black for visible
        else:
            label.setText(name, color='#888888') # Grey for hidden

class CumulativePlot(QTabWidget):
    """A tabbed widget to display cumulative plots for multiple barcodes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.barcode_plots = {} 

    def update_data(self, data_file):
        if not os.path.exists(data_file):
            return
        try:
            df = pd.read_csv(data_file)
            if df.empty: return

            df['barcode'] = df['barcode'].str.strip()
            all_barcodes = df['barcode'].unique()

            for barcode in all_barcodes:
                if barcode not in self.barcode_plots:
                    plot_widget = SingleBarcodePlot(barcode)
                    self.barcode_plots[barcode] = plot_widget
                    self.addTab(plot_widget, barcode)

            for barcode, plot_widget in self.barcode_plots.items():
                barcode_df = df[df['barcode'] == barcode].copy()
                plot_widget.update_plot_data(barcode_df)

        except Exception as e:
            print(f"Error processing data file {data_file}: {e}")

