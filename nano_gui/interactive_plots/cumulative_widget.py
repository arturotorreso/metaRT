# nano_gui/interactive_plots/cumulative_widget.py
import os
import pandas as pd
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QSlider, QScrollArea, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt

# Professional muted palette (Tableau 10)
TABLEAU_COLORS = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', 
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'
]

class DataLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)
    failed = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if not os.path.exists(self.file_path):
                return
            if os.path.getsize(self.file_path) == 0:
                self.data_loaded.emit(pd.DataFrame())
                return
            df = pd.read_csv(self.file_path)
            self.data_loaded.emit(df)
        except Exception as e:
            self.failed.emit(str(e))

class SingleBarcodePlot(QWidget):
    def __init__(self, barcode, parent=None):
        super().__init__(parent)
        self.barcode = barcode
        self.last_df = pd.DataFrame() 

        # --- MAIN VERTICAL LAYOUT ---
        main_layout = QVBoxLayout(self)

        # 1. Controls Toolbar (Slider)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Show Top N Species:"))
        
        # Slider
        self.species_slider = QSlider(Qt.Orientation.Horizontal)
        self.species_slider.setRange(1, 50) # Start with safe default
        self.species_slider.setValue(10)
        self.species_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.species_slider.setTickInterval(5)
        
        # Label to show slider value
        self.slider_value_label = QLabel("10")
        self.slider_value_label.setFixedWidth(40)
        self.slider_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Connect slider
        self.species_slider.valueChanged.connect(self.on_slider_value_changed)
        
        controls_layout.addWidget(self.species_slider)
        controls_layout.addWidget(self.slider_value_label)
        controls_layout.addStretch() 
        
        main_layout.addLayout(controls_layout)

        # 2. Content Layout (Plot + Scrollable Legend)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # --- A. PLOT WIDGET (LEFT) ---
        self.plot_widget = pg.PlotWidget(background='w')
        self.plot_widget.setTitle(f"Cumulative Reads for {barcode}", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Cumulative Read Count', color='k')
        self.plot_widget.setLabel('bottom', 'Time', color='k')
        self.plot_widget.setLogMode(y=True)
        self.plot_widget.getAxis('left').setTextPen('k')
        self.plot_widget.getAxis('bottom').setTextPen('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setDownsampling(mode='peak')
        self.plot_widget.setClipToView(True)
        
        self.date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.date_axis})
        
        content_layout.addWidget(self.plot_widget, stretch=1)

        # --- B. SCROLLABLE LEGEND (RIGHT) ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedWidth(220) # Fixed width for legend area
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.legend_container = QWidget()
        self.legend_layout = QVBoxLayout(self.legend_container)
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.legend_layout.setContentsMargins(10, 0, 0, 0)
        self.legend_layout.setSpacing(5) # Spacing between items
        
        self.scroll_area.setWidget(self.legend_container)
        content_layout.addWidget(self.scroll_area)

        self.curves = {} 
    
    def on_slider_value_changed(self, value):
        """Updates label and plot when slider moves."""
        self.slider_value_label.setText(str(value))
        self.refresh_plot()

    def update_plot_data(self, barcode_df):
        if barcode_df.empty: return
        self.last_df = barcode_df
        
        # --- DYNAMIC SLIDER UPDATE ---
        try:
            total_species = barcode_df['name'].nunique()
            if total_species > 0:
                self.species_slider.setMaximum(total_species)
                
                # Ticks update
                if total_species > 50:
                    self.species_slider.setTickInterval(10)
                else:
                    self.species_slider.setTickInterval(5)
        except Exception as e:
            print(f"Error updating cumulative slider: {e}")

        self.refresh_plot()

    def refresh_plot(self):
        try:
            if self.last_df.empty: return

            df = self.last_df.copy()
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                 df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Get value from slider
            top_n = self.species_slider.value()

            latest_timestamp = df['timestamp'].max()
            latest_data = df[df['timestamp'] == latest_timestamp]
            if latest_data.empty: return

            sorted_latest = latest_data.sort_values('cumulative_reads', ascending=False)
            top_species_ordered = sorted_latest.head(top_n)['name'].tolist()
            
            plot_df = df[df['name'].isin(top_species_ordered)]
            if plot_df.empty: return

            current_species_in_plot = set()

            # Clear existing legend items
            self._clear_legend()

            for i, species_name in enumerate(top_species_ordered):
                group = plot_df[plot_df['name'] == species_name]
                if group.empty: continue

                sorted_group = group.sort_values('timestamp')
                x_data = (sorted_group['timestamp'].astype('int64') / 10**9).to_numpy()
                y_raw = sorted_group['cumulative_reads'].to_numpy()
                y_data = np.maximum(y_raw, 0.1)
                
                current_species_in_plot.add(species_name)

                # Color
                hex_color = TABLEAU_COLORS[i % len(TABLEAU_COLORS)]
                pen = pg.mkPen(color=hex_color, width=2)

                # Plot Curve
                if species_name in self.curves:
                    self.curves[species_name].setData(x_data, y_data, pen=pen)
                    if not self.curves[species_name].isVisible():
                        self.curves[species_name].show()
                else:
                    curve = self.plot_widget.plot(x_data, y_data, pen=pen)
                    self.curves[species_name] = curve

                # Add to Scrollable Legend
                self._add_legend_item(species_name, hex_color)

            # Hide unused curves
            for name, curve in self.curves.items():
                if name not in current_species_in_plot:
                    curve.hide()

        except Exception as e:
            print(f"Error updating cumulative plot: {e}")

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

        # Color Box
        color_box = QLabel()
        color_box.setFixedSize(12, 12)
        color_box.setStyleSheet(f"background-color: {color_hex}; border-radius: 2px;")
        
        # Text
        text_label = QLabel(name)
        text_label.setStyleSheet("font-size: 10pt; color: #333;")
        text_label.setWordWrap(True)

        h_layout.addWidget(color_box)
        h_layout.addWidget(text_label)
        h_layout.addStretch()

        self.legend_layout.addWidget(item_widget)

class CumulativePlot(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.barcode_plots = {} 
        self.loader = None 
        
        self.no_data_label = QLabel("Waiting for data...\n(Pipeline output not found yet)", self)
        self.no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_data_label.setStyleSheet("color: gray; font-size: 14pt;")
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.no_data_label)

    def update_data(self, data_file):
        if not os.path.exists(data_file): return
        if self.loader is not None and self.loader.isRunning(): return

        self.loader = DataLoader(data_file)
        self.loader.data_loaded.connect(self.on_data_loaded)
        self.loader.start()

    @pyqtSlot(pd.DataFrame)
    def on_data_loaded(self, df):
        if df.empty: return
        try:
            if not df.empty and self.no_data_label.isVisible():
                self.no_data_label.hide()

            if 'barcode' not in df.columns: return
                
            df['barcode'] = df['barcode'].astype(str).str.strip()
            all_barcodes = df['barcode'].unique()

            for barcode in all_barcodes:
                if barcode not in self.barcode_plots:
                    plot_widget = SingleBarcodePlot(barcode)
                    self.barcode_plots[barcode] = plot_widget
                    self.addTab(plot_widget, barcode)

            current_idx = self.currentIndex()
            if current_idx != -1:
                current_barcode = self.tabText(current_idx)
                if current_barcode in self.barcode_plots:
                    barcode_df = df[df['barcode'] == current_barcode].copy()
                    self.barcode_plots[current_barcode].update_plot_data(barcode_df)
                    
        except Exception as e:
            print(f"Error processing accumulation data: {e}")