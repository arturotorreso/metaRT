# nano_gui/ui_windows/taxonomy.py
import os
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QSplitter)
from PyQt6.QtCore import Qt
from interactive_plots.rarefaction_widget import RarefactionPlot

import glob

class TaxonomyWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # --- Top 10 Species Table ---
        table_group = QGroupBox("Top 10 Species per Barcode")
        table_layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Barcode", "Species Name", "Estimated Reads"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        
        # --- Rarefaction Plot ---
        plot_group = QGroupBox("Rarefaction Curve")
        plot_layout = QVBoxLayout()
        self.rarefaction_plot = RarefactionPlot()
        plot_layout.addWidget(self.rarefaction_plot)
        plot_group.setLayout(plot_layout)
        
        splitter.addWidget(table_group)
        splitter.addWidget(plot_group)
        splitter.setSizes([200, 500]) # Give more space to the plot
        layout.addWidget(splitter)

    def update_data(self, config):
        output_dir = config.get('Paths', 'output_directory')
        agg_dir = os.path.join(output_dir, "aggregated_results")
        
        # --- Update Table ---
        self.table.setRowCount(0) # Clear table
        all_barcodes_df = []
        for barcode_dir in glob.glob(os.path.join(agg_dir, "barcode*")):
            bracken_file = os.path.join(barcode_dir, f"master_{os.path.basename(barcode_dir)}.bracken_sp.tsv")
            if os.path.exists(bracken_file):
                df = pd.read_csv(bracken_file, sep='\t')
                df['barcode'] = os.path.basename(barcode_dir)
                top10 = df.nlargest(10, 'new_est_reads')
                all_barcodes_df.append(top10)

        if all_barcodes_df:
            final_df = pd.concat(all_barcodes_df)
            self.table.setRowCount(len(final_df))
            for i, row in enumerate(final_df.itertuples()):
                self.table.setItem(i, 0, QTableWidgetItem(row.barcode))
                self.table.setItem(i, 1, QTableWidgetItem(row.name))
                self.table.setItem(i, 2, QTableWidgetItem(str(row.new_est_reads)))

        # --- Update Plot ---
        rarefaction_log = os.path.join(agg_dir, "rarefaction_data.csv")
        self.rarefaction_plot.update_data(rarefaction_log)