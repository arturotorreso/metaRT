# nano_gui/ui_windows/abundance.py
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QScrollArea
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class AbundanceWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        vbox = QVBoxLayout(scroll_content)
        
        # Absolute Abundance
        abs_group = QGroupBox("Absolute Abundance")
        abs_layout = QVBoxLayout()
        self.abs_plot_label = QLabel("Plot will appear here after first batch.")
        self.abs_plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        abs_layout.addWidget(self.abs_plot_label)
        abs_group.setLayout(abs_layout)
        vbox.addWidget(abs_group)
        
        # Relative Abundance
        rel_group = QGroupBox("Relative Abundance")
        rel_layout = QVBoxLayout()
        self.rel_plot_label = QLabel("Plot will appear here after first batch.")
        self.rel_plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rel_layout.addWidget(self.rel_plot_label)
        rel_group.setLayout(rel_layout)
        vbox.addWidget(rel_group)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def update_data(self, config):
        output_dir = config.get('Paths', 'output_directory')
        agg_dir = os.path.join(output_dir, "aggregated_results")
        
        # Load and display the absolute abundance plot
        abs_plot_path = os.path.join(agg_dir, "absolute_abundance_barplot.png")
        if os.path.exists(abs_plot_path):
            pixmap = QPixmap(abs_plot_path)
            self.abs_plot_label.setPixmap(pixmap.scaled(self.abs_plot_label.size(), 
                                                       Qt.AspectRatioMode.KeepAspectRatio, 
                                                       Qt.TransformationMode.SmoothTransformation))
        
        # Load and display the relative abundance plot
        rel_plot_path = os.path.join(agg_dir, "relative_abundance_barplot.png")
        if os.path.exists(rel_plot_path):
            pixmap = QPixmap(rel_plot_path)
            self.rel_plot_label.setPixmap(pixmap.scaled(self.rel_plot_label.size(),
                                                       Qt.AspectRatioMode.KeepAspectRatio, 
                                                       Qt.TransformationMode.SmoothTransformation))