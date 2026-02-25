# nano_gui/ui_windows/accumulation.py
import os
import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from interactive_plots.cumulative_widget import CumulativePlot

class AccumulationWindow(QWidget):
    """
    A window to display cumulative read plots for all barcodes.
    """
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_layout = QVBoxLayout()
        self.title_label = QLabel("Cumulative Read Counts per Species")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-size: 10pt; color: #666;")
        
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.status_label)
        self.main_layout.addLayout(title_layout)

        self.plot_widget = CumulativePlot()
        self.main_layout.addWidget(self.plot_widget)
        
        self.data_file_path = None

    def update_data(self, config):
        if not self.data_file_path:
            output_dir = config.get('Paths', 'output_directory', fallback='')
            if not output_dir:
                self.status_label.setText("Status: Config Error - 'output_directory' missing")
                return
            
            agg_dir = os.path.join(output_dir, "aggregated_results")
            self.data_file_path = os.path.join(agg_dir, "cumulative_species_data.csv")

        if not os.path.exists(self.data_file_path):
            self.status_label.setText(f"Status: Waiting for pipeline output... ({os.path.basename(self.data_file_path)} not found)")
            return 

        try:
            if os.path.getsize(self.data_file_path) == 0:
                self.status_label.setText("Status: File found but empty. Waiting for data...")
                return

            self.plot_widget.update_data(self.data_file_path)
            
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.status_label.setText(f"Status: Data loaded at {timestamp}")

        except Exception as e:
            self.status_label.setText(f"Status: Error - {str(e)[:50]}")
            print(f"Accumulation Update Error: {e}")
