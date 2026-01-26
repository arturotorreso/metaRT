# nano_gui/ui_windows/taxonomy.py
import os
import glob
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from interactive_plots.rarefaction_widget import RarefactionPlot

# --- Worker Thread for Table Data ---
class TableLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)

    def __init__(self, agg_dir):
        super().__init__()
        self.agg_dir = agg_dir

    def run(self):
        # This loop does multiple IO operations, essential to move off main thread
        all_barcodes_df = []
        try:
            # Look for all barcode folders
            for barcode_dir in glob.glob(os.path.join(self.agg_dir, "barcode*")):
                bracken_file = os.path.join(barcode_dir, f"master_{os.path.basename(barcode_dir)}.bracken_sp.tsv")
                
                if os.path.exists(bracken_file):
                    # Heavy CSV parsing here
                    df = pd.read_csv(bracken_file, sep='\t')
                    if not df.empty:
                        df['barcode'] = os.path.basename(barcode_dir)
                        # Sorting and slicing
                        top10 = df.nlargest(10, 'new_est_reads')
                        all_barcodes_df.append(top10)

            if all_barcodes_df:
                final_df = pd.concat(all_barcodes_df)
                self.data_loaded.emit(final_df)
            else:
                self.data_loaded.emit(pd.DataFrame()) # Emit empty if nothing found
                
        except Exception as e:
            print(f"Table load error: {e}")

class TaxonomyWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()
        self.table_loader = None # Thread holder

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
        # Boutique styling for table
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { gridline-color: #d0d0d0; }")
        
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
        splitter.setSizes([250, 450]) 
        layout.addWidget(splitter)

    def update_data(self, config):
        output_dir = config.get('Paths', 'output_directory')
        agg_dir = os.path.join(output_dir, "aggregated_results")
        
        # 1. Update Plot (This is now non-blocking thanks to Step 1)
        rarefaction_log = os.path.join(agg_dir, "rarefaction_data.csv")
        self.rarefaction_plot.update_data(rarefaction_log)

        # 2. Update Table (Now using threaded loader)
        if self.table_loader is not None and self.table_loader.isRunning():
            return # Skip if already loading
            
        self.table_loader = TableLoader(agg_dir)
        self.table_loader.data_loaded.connect(self.on_table_data_loaded)
        self.table_loader.start()

    @pyqtSlot(pd.DataFrame)
    def on_table_data_loaded(self, final_df):
        """Populate table only when data is ready."""
        if final_df.empty:
            return

        self.table.setRowCount(len(final_df))
        self.table.setSortingEnabled(False) # Disable sorting while inserting

        for i, row in enumerate(final_df.itertuples()):
            # Safe access to attributes
            barcode = getattr(row, 'barcode', 'N/A')
            name = getattr(row, 'name', 'Unknown')
            reads = getattr(row, 'new_est_reads', 0)

            self.table.setItem(i, 0, QTableWidgetItem(str(barcode)))
            self.table.setItem(i, 1, QTableWidgetItem(str(name)))
            self.table.setItem(i, 2, QTableWidgetItem(str(reads)))
        
        self.table.setSortingEnabled(True)