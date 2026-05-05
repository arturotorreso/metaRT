import os
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class AntibiogramWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        title = QLabel("Clinical Antibiogram (Organism vs Drug Class)")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #3c5457;")
        self.layout.addWidget(title)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self.last_mtimes = {}

    def update_data(self, config):
        """Called automatically every 15 seconds by the main GUI timer."""
        output_dir = config.get('Paths', 'output_directory', fallback=None)
        if not output_dir: return
        
        agg_dir = os.path.join(output_dir, "aggregated_results")
        if not os.path.exists(agg_dir): return
        
        # Scan for all Antibiogram JSONs
        for barcode in sorted(os.listdir(agg_dir)):
            anti_path = os.path.join(agg_dir, barcode, f"master_{barcode}.antibiogram.json")
            if os.path.exists(anti_path):
                mtime = os.path.getmtime(anti_path)
                if self.last_mtimes.get(barcode) != mtime:
                    self.last_mtimes[barcode] = mtime
                    self._render_antibiogram(barcode, anti_path)

    def _render_antibiogram(self, barcode, json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
        except Exception: return
        
        # Collect all unique drug classes to form the columns
        drug_classes = set()
        for org, classes in data.items():
            for dc in classes.keys():
                drug_classes.add(dc)
        
        drug_classes = sorted(list(drug_classes))
        organisms = sorted(list(data.keys()))
        
        # Ensure the Unassigned elements are pinned to the bottom of the matrix
        if "Unassigned / Mobile Elements" in organisms:
            organisms.remove("Unassigned / Mobile Elements")
            organisms.append("Unassigned / Mobile Elements")

        # Initialize the Table Matrix
        table = QTableWidget(len(organisms), len(drug_classes))
        table.setHorizontalHeaderLabels(drug_classes)
        table.setVerticalHeaderLabels(organisms)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Populate the Matrix
        for row, org in enumerate(organisms):
            for col, dc in enumerate(drug_classes):
                genes = data[org].get(dc, [])
                if genes:
                    cell_text = "R (" + ", ".join(genes) + ")"
                    item = QTableWidgetItem(cell_text)
                    item.setToolTip("\n".join(genes)) # Hover tooltip for full list
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setBackground(QColor("#A94442")) # Muted Red
                    item.setForeground(QColor("#ffffff"))
                    table.setItem(row, col, item)
                else:
                    item = QTableWidgetItem("-")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, col, item)

        # Update or add the Tab
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == barcode:
                self.tabs.removeTab(i)
                self.tabs.insertTab(i, table, barcode)
                self.tabs.setCurrentIndex(i)
                return
        
        self.tabs.addTab(table, barcode)