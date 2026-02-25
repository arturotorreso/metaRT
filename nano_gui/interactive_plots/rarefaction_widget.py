# nano_gui/interactive_plots/rarefaction_widget.py
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QLabel, QFrame)
from PyQt6.QtCore import Qt

TABLEAU_COLORS = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', 
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'
]

class RarefactionPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Main Layout
        layout = QHBoxLayout(self)
        
        # 1. Plot Widget
        self.plot_widget = pg.PlotWidget(background='w')
        self.plot_widget.setTitle("Rarefaction Curve", color='k', size='12pt')
        self.plot_widget.setLabel('left', 'Unique Species Found', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.plot_widget.getAxis('left').setTextPen('k')
        self.plot_widget.getAxis('bottom').setTextPen('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        
        layout.addWidget(self.plot_widget, stretch=1)
        
        # 2. Scrollable Legend Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedWidth(220)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.legend_container = QWidget()
        self.legend_layout = QVBoxLayout(self.legend_container)
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.legend_layout.setContentsMargins(10, 0, 0, 0)
        self.legend_layout.setSpacing(5)

        self.scroll_area.setWidget(self.legend_container)
        layout.addWidget(self.scroll_area)
        
        self.curves = {}

    def update_data(self, file_path):
        """Loads CSV and updates curves."""
        try:
            df = pd.read_csv(file_path)
            if df.empty: return
            
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            barcodes = df['barcode'].unique()
            
            # Clear legend to rebuild
            self._clear_legend()
            
            for i, barcode in enumerate(barcodes):
                subset = df[df['barcode'] == barcode].sort_values('timestamp')
                x_data = (subset['timestamp'].astype('int64') / 10**9).to_numpy()
                y_data = subset['unique_species_count'].to_numpy()
                
                color_hex = TABLEAU_COLORS[i % len(TABLEAU_COLORS)]
                pen = pg.mkPen(color=color_hex, width=2)
                
                if barcode in self.curves:
                    self.curves[barcode].setData(x_data, y_data, pen=pen)
                else:
                    curve = self.plot_widget.plot(x_data, y_data, pen=pen)
                    self.curves[barcode] = curve
                
                # Add to scrollable legend
                self._add_legend_item(barcode, color_hex)
                    
        except Exception as e:
            print(f"Rarefaction update error: {e}")

    def _clear_legend(self):
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_legend_item(self, name, color_hex):
        item_widget = QWidget()
        h_layout = QHBoxLayout(item_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        color_box = QLabel()
        color_box.setFixedSize(12, 12)
        color_box.setStyleSheet(f"background-color: {color_hex}; border-radius: 2px;")
        
        text_label = QLabel(name)
        text_label.setStyleSheet("font-size: 10pt; color: #333;")
        text_label.setWordWrap(True)

        h_layout.addWidget(color_box)
        h_layout.addWidget(text_label)
        h_layout.addStretch()

        self.legend_layout.addWidget(item_widget)