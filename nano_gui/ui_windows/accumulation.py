# nano_gui/ui_windows/accumulation.py
import os
import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
# The relative import path is correct for the main application
from interactive_plots.cumulative_widget import CumulativePlot

class AccumulationWindow(QWidget):
    """
    A window to display cumulative read plots for all barcodes, using a single
    tabbed widget and looking for the correct data file path.
    """
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_layout = QVBoxLayout()
        self.title_label = QLabel("Cumulative Read Counts per Species")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        # Status label for clear diagnostics
        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setStyleSheet("font-size: 10pt; color: #666;")
        
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.status_label)
        self.main_layout.addLayout(title_layout)

        # The single, self-managing tabbed plot widget
        self.plot_widget = CumulativePlot()
        self.main_layout.addWidget(self.plot_widget)
        
        self.data_file_path = None

    def update_data(self, config):
        """
        Updates the data for the cumulative plot widget using the correct, nested file path.
        """
        if not self.data_file_path:
            output_dir = config.get('Paths', 'output_directory', fallback='')
            if not output_dir:
                self.status_label.setText("Status: Error - 'output_directory' not set in config.ini")
                return
            
            # --- CORRECTED FILE PATH LOGIC ---
            # As you pointed out, the data is in a subdirectory.
            agg_dir = os.path.join(output_dir, "aggregated_results")
            self.data_file_path = os.path.join(agg_dir, "cumulative_species_data.csv")

        # --- Enhanced Diagnostic Checks ---
        if not os.path.exists(self.data_file_path):
            self.status_label.setText(f"Status: Waiting for data file... (Not found: {self.data_file_path})")
            return 

        try:
            if os.path.getsize(self.data_file_path) == 0:
                self.status_label.setText("Status: Data file is empty. Waiting for results...")
                return

            self.plot_widget.update_data(self.data_file_path)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.status_label.setText(f"Status: Plot updated successfully at {timestamp}")

        except Exception as e:
            self.status_label.setText(f"Status: Error updating plot - {e}")
            print(f"Failed to update accumulation plot: {e}")

