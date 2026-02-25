# nano_gui/ui_windows/abundance.py
import os
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QLabel, QSlider, QScrollArea, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt

TABLEAU_COLORS = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', 
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'
]

class AbundanceLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if os.path.exists(self.file_path):
                df = pd.read_csv(self.file_path)
                self.data_loaded.emit(df)
        except Exception as e:
            print(f"Abundance load error: {e}")

class StackedBarPlotWidget(QWidget):
    def __init__(self, title, y_label, parent=None):
        super().__init__(parent)
        
        # Main Layout: Horizontal to hold Plot (left) and Legend (right)
        layout = QHBoxLayout(self)
        
        # 1. Plot Widget
        self.plot_widget = pg.PlotWidget(background='w')
        self.plot_widget.setTitle(title, color='k', size='12pt')
        self.plot_widget.setLabel('left', y_label, color='k')
        self.plot_widget.showGrid(y=True, alpha=0.3)
        self.plot_widget.getAxis('left').setTextPen('k')

        self.x_axis = self.plot_widget.getAxis('bottom')
        self.x_axis.setPen('k')
        self.x_axis.setTextPen('k')
        
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

    def update_plot(self, df, value_col, top_n=15):
        self.plot_widget.clear()
        self._clear_legend()
        
        if df.empty: return

        pivot_df = df.pivot_table(index='barcode', columns='name', values=value_col, fill_value=0)
        
        # Ensure we don't try to get more species than exist
        actual_top_n = min(top_n, pivot_df.shape[1])
        top_species = pivot_df.sum().nlargest(actual_top_n).index
        pivot_df = pivot_df[top_species]
        
        barcodes = pivot_df.index.tolist()
        x = np.arange(len(barcodes))

        ticks = [list(zip(x, barcodes))]
        self.x_axis.setTicks(ticks)

        bottom = np.zeros(len(barcodes))
        
        for i, species in enumerate(top_species):
            heights = pivot_df[species].values
            
            # Cyclic color selection
            hex_color = TABLEAU_COLORS[i % len(TABLEAU_COLORS)]
            color = pg.mkColor(hex_color)
            brush = pg.mkBrush(color)
            
            bar = pg.BarGraphItem(
                x=x, 
                y0=bottom, 
                height=heights, 
                width=0.6, 
                brush=brush, 
                pen=pg.mkPen('w', width=1),
                name=species
            )
            
            self.plot_widget.addItem(bar)
            self._add_legend_item(species, hex_color)
            
            bottom += heights

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

class AbundanceWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Species to Show:"))
        
        # Slider
        self.top_n_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_n_slider.setRange(1, 50) # Initial range
        self.top_n_slider.setValue(15)
        self.top_n_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.top_n_slider.setTickInterval(5)

        # Label for slider value
        self.slider_value_label = QLabel("15")
        self.slider_value_label.setFixedWidth(40)
        self.slider_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Connect Slider
        self.top_n_slider.valueChanged.connect(self.on_slider_value_changed)
        
        ctrl_layout.addWidget(self.top_n_slider)
        ctrl_layout.addWidget(self.slider_value_label)
        ctrl_layout.addStretch()
        self.layout.addLayout(ctrl_layout)

        self.tabs = QTabWidget()
        self.abs_plot = StackedBarPlotWidget("Absolute Abundance", "Read Count")
        self.rel_plot = StackedBarPlotWidget("Relative Abundance", "Percentage (%)")
        
        self.tabs.addTab(self.abs_plot, "Absolute")
        self.tabs.addTab(self.rel_plot, "Relative")
        
        self.layout.addWidget(self.tabs)
        
        self.loader = None
        self.cached_df = pd.DataFrame()
        
    def on_slider_value_changed(self, value):
        """Updates label and refreshes plots."""
        self.slider_value_label.setText(str(value))
        self.refresh_plots()

    def update_data(self, config):
        output_dir = config.get('Paths', 'output_directory')
        csv_path = os.path.join(output_dir, "aggregated_results", "abundance_data.csv")
        
        if not os.path.exists(csv_path): return

        if self.loader is not None and self.loader.isRunning(): return

        self.loader = AbundanceLoader(csv_path)
        self.loader.data_loaded.connect(self.on_data_loaded)
        self.loader.start()

    @pyqtSlot(pd.DataFrame)
    def on_data_loaded(self, df):
        if df.empty: return
        self.cached_df = df
        
        # --- DYNAMIC SLIDER RANGE UPDATE ---
        try:
            if 'name' in df.columns:
                total_species = df['name'].nunique()
                
                # If total species increased beyond current max, update slider
                if total_species > 0:
                    # Update range to allow selecting all available species
                    # We keep min at 1, max at total_species
                    self.top_n_slider.setMaximum(total_species)
                    
                    # Adjust tick interval for better visibility
                    if total_species > 50:
                        self.top_n_slider.setTickInterval(10)
                    elif total_species > 20:
                        self.top_n_slider.setTickInterval(5)
                    else:
                        self.top_n_slider.setTickInterval(1)
        except Exception as e:
            print(f"Error updating abundance slider: {e}")

        self.refresh_plots()

    def refresh_plots(self):
        if self.cached_df.empty: return
        # Get value from slider
        top_n = self.top_n_slider.value()
        
        if 'absolute_abundance' in self.cached_df.columns:
            self.abs_plot.update_plot(self.cached_df, 'absolute_abundance', top_n)
        if 'relative_abundance' in self.cached_df.columns:
            self.rel_plot.update_plot(self.cached_df, 'relative_abundance', top_n)