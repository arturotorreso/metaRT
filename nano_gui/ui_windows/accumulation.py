# nano_gui/ui_windows/accumulation.py
import os
import glob
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QGroupBox
from interactive_plots.cumulative_widget import CumulativePlot

class AccumulationWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_widgets = {}
        self.setupUi()

    def setupUi(self):
        self.main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        self.main_layout.addWidget(scroll)

    def update_data(self, config):
        output_dir = config.get('Paths', 'output_directory')
        agg_dir = os.path.join(output_dir, "aggregated_results")
        cumulative_log = os.path.join(agg_dir, "cumulative_species_data.csv")
        
        # Discover barcodes
        barcodes = [os.path.basename(p) for p in glob.glob(os.path.join(agg_dir, "barcode*"))]
        
        # Create or update plots for each barcode
        for barcode in sorted(barcodes):
            if barcode not in self.plot_widgets:
                group = QGroupBox(f"Cumulative Plot: {barcode}")
                layout = QVBoxLayout()
                plot = CumulativePlot(barcode=barcode)
                layout.addWidget(plot)
                group.setLayout(layout)
                self.scroll_layout.addWidget(group)
                self.plot_widgets[barcode] = plot
            
            # Tell the plot to refresh its data
            self.plot_widgets[barcode].update_data(cumulative_log)