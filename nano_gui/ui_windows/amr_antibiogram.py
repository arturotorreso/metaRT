import os
import json
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QLabel, QSpinBox, QDoubleSpinBox, QStyleOptionHeader, QStyle)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter

class RotatedHeaderView(QHeaderView):
    """Custom Header View to rotate column text 45 degrees for better fitting."""
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        # Increased minimum height significantly to accommodate very long drug classes
        self.setMinimumHeight(280)  
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setDefaultSectionSize(120)

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        
        # Turn on anti-aliasing for smooth diagonal text
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Draw the native background border/button style for the header
        opt = QStyleOptionHeader()
        opt.initFrom(self)
        opt.rect = rect
        opt.section = logicalIndex
        opt.text = "" # We will draw the text manually
        self.style().drawControl(QStyle.ControlElement.CE_HeaderSection, opt, painter, self)
        
        # Draw the text rotated at -45 degrees
        text = self.model().headerData(logicalIndex, self.orientation(), Qt.ItemDataRole.DisplayRole)
        if text:
            # Shift the painter origin to the bottom-left of the cell, then rotate
            painter.translate(rect.x() + 20, rect.y() + rect.height() - 15)
            painter.rotate(-45)
            painter.drawText(0, 0, str(text))
            
        painter.restore()


class AntibiogramWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        title = QLabel("Clinical Antibiogram (Organism vs Drug Class)")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px; color: #3c5457;")
        self.layout.addWidget(title)
        
        # --- Control Panel for Filtering ---
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("Show Top Species:"))
        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(0, 500)
        self.top_n_spin.setValue(10) # Default to 10
        self.top_n_spin.setToolTip("Set to 0 to show all detected species")
        self.top_n_spin.valueChanged.connect(self._refresh_all_tabs)
        control_layout.addWidget(self.top_n_spin)
        
        control_layout.addWidget(QLabel(" Min Clade Reads:"))
        self.min_reads_spin = QSpinBox()
        self.min_reads_spin.setRange(0, 1000000)
        self.min_reads_spin.setValue(100) # Default to 100
        self.min_reads_spin.valueChanged.connect(self._refresh_all_tabs)
        control_layout.addWidget(self.min_reads_spin)
        
        control_layout.addWidget(QLabel(" Min Abundance (%):"))
        self.min_abund_spin = QDoubleSpinBox()
        self.min_abund_spin.setRange(0.0, 100.0)
        self.min_abund_spin.setDecimals(3) # Allow fine decimals
        self.min_abund_spin.setSingleStep(0.1)
        self.min_abund_spin.setValue(0.01) # Default to 0.01%
        self.min_abund_spin.valueChanged.connect(self._refresh_all_tabs)
        control_layout.addWidget(self.min_abund_spin)
        
        control_layout.addStretch()
        self.layout.addLayout(control_layout)
        
        # --- Main Tab Widget ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Cache to store data so changing SpinBoxes is instant
        self.barcode_data = {} 
        self.last_mtimes = {}

    def update_data(self, config):
        """Called automatically every 15 seconds by the main GUI timer."""
        output_dir = config.get('Paths', 'output_directory', fallback=None)
        if not output_dir: return
        
        agg_dir = os.path.join(output_dir, "aggregated_results")
        if not os.path.exists(agg_dir): return
        
        data_changed = False
        
        # Scan for all Antibiogram JSONs and Bracken TSVs
        for barcode in sorted(os.listdir(agg_dir)):
            anti_path = os.path.join(agg_dir, barcode, f"master_{barcode}.antibiogram.json")
            rep_path = os.path.join(agg_dir, barcode, f"master_{barcode}.report.tsv")
            
            if os.path.exists(anti_path):
                mtime = os.path.getmtime(anti_path)
                if self.last_mtimes.get(barcode) != mtime:
                    self.last_mtimes[barcode] = mtime
                    
                    # 1. Load the AMR Matrix Data
                    try:
                        with open(anti_path, 'r') as f:
                            anti_data = json.load(f)
                    except Exception: continue
                    
                    # 2. Load the Bracken Abundance Data (for filtering)
                    org_stats = {}
                    if os.path.exists(rep_path):
                        try:
                            # Bracken format: pct (0), reads (1), name (5)
                            df = pd.read_csv(rep_path, sep='\t', header=None, names=['pct', 'reads', 'lreads', 'lvl', 'taxid', 'name'])
                            for _, row in df.iterrows():
                                org_stats[str(row['name']).strip()] = {
                                    'reads': int(row['reads']),
                                    'pct': float(row['pct'])
                                }
                        except Exception: pass
                    
                    # Save to internal dictionary
                    self.barcode_data[barcode] = {
                        'antibiogram': anti_data,
                        'abundance': org_stats
                    }
                    data_changed = True
                    
        if data_changed:
            self._refresh_all_tabs()

    def _refresh_all_tabs(self):
        """Rebuilds the tables when new data arrives OR when spinboxes are changed."""
        # Preserve current tab so the UI doesn't jump around
        current_idx = self.tabs.currentIndex()
        current_barcode = self.tabs.tabText(current_idx) if current_idx >= 0 else None
        
        self.tabs.clear()
        
        for barcode, data in self.barcode_data.items():
            table = self._build_table_widget(data['antibiogram'], data['abundance'])
            self.tabs.addTab(table, barcode)
            
        if current_barcode:
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == current_barcode:
                    self.tabs.setCurrentIndex(i)
                    break

    def _build_table_widget(self, anti_data, abundance_data):
        """Builds a single QTableWidget using the current spinbox filters."""
        top_n = self.top_n_spin.value()
        min_reads = self.min_reads_spin.value()
        min_abund = self.min_abund_spin.value()
        
        # 1. Collect all unique drug classes to form the columns
        drug_classes = set()
        for org, classes in anti_data.items():
            for dc in classes.keys():
                drug_classes.add(dc)
        drug_classes = sorted(list(drug_classes))
        
        # 2. Filter & Sort Organisms based on Bracken Abundance
        unassigned_key = "Unassigned / Mobile Elements"
        raw_orgs = [o for o in anti_data.keys() if o != unassigned_key]
        
        # Map to (Organism, Read Count) and filter by min_reads AND min_abundance
        org_tuples = []
        for org in raw_orgs:
            stats = abundance_data.get(org, {'reads': 0, 'pct': 0.0})
            reads = stats['reads']
            pct = stats['pct']
            
            if reads >= min_reads and pct >= min_abund:
                org_tuples.append((org, reads))
                
        # Sort by read count descending
        org_tuples.sort(key=lambda x: x[1], reverse=True)
        
        # Slice for Top N
        if top_n > 0:
            org_tuples = org_tuples[:top_n]
            
        organisms = [o[0] for o in org_tuples]
        
        # Always pin Plasmids/Unassigned to the bottom if they exist
        if unassigned_key in anti_data:
            organisms.append(unassigned_key)

        # 3. Initialize the Table Matrix
        table = QTableWidget(len(organisms), len(drug_classes))
        
        # Set Custom Rotated Headers
        header = RotatedHeaderView()
        table.setHorizontalHeader(header)
        table.setHorizontalHeaderLabels(drug_classes)
        table.setVerticalHeaderLabels(organisms)
        
        # Enable Resizing and Scrolling
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 4. Populate the Matrix
        for row, org in enumerate(organisms):
            for col, dc in enumerate(drug_classes):
                genes = anti_data[org].get(dc, [])
                if genes:
                    # Show clean "R", hide marker data in the tooltip
                    item = QTableWidgetItem("R")
                    item.setToolTip("\n".join(genes)) 
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setBackground(QColor("#A94442")) # Muted Red
                    item.setForeground(QColor("#ffffff"))
                    table.setItem(row, col, item)
                else:
                    item = QTableWidgetItem("-")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, col, item)

        return table