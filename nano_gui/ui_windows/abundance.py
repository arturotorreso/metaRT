# nano_gui/ui_windows/abundance.py
import os
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot

# --- Worker Thread ---
class AbundanceLoader(QThread):
    data_loaded = pyqtSignal(pd.DataFrame)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if os.path.exists(self.file_path):
                # Load CSV
                df = pd.read_csv(self.file_path)
                self.data_loaded.emit(df)
        except Exception as e:
            print(f"Abundance load error: {e}")

# --- Interactive Stacked Bar Widget ---
class StackedBarPlotWidget(QWidget):
    def __init__(self, title, y_label, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Plot Setup
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(title, color='k', size='12pt')
        self.plot_widget.setLabel('left', y_label, color='k')
        self.plot_widget.showGrid(y=True, alpha=0.3)
        
        # Custom Axis for Strings (Barcodes)
        self.x_axis = self.plot_widget.getAxis('bottom')
        self.x_axis.setPen('k')
        self.x_axis.setTextPen('k')
        
        # Legend
        self.legend = self.plot_widget.addLegend(offset=(30, 30))
        self.legend.setBrush(pg.mkBrush(255,255,255,200)) # Semi-transparent white
        self.legend.setPen(pg.mkPen('d'))

        self.layout.addWidget(self.plot_widget)
        self.bars = [] # Keep track of bar items to clear later

    def update_plot(self, df, value_col):
        """
        df: DataFrame with columns ['barcode', 'name', value_col]
        value_col: 'absolute_abundance' or 'relative_abundance'
        """
        self.plot_widget.clear()
        self.legend.clear() # Clear old legend items
        
        if df.empty: return

        # 1. Pivot Data: Index=Barcode, Columns=Species, Values=Count
        pivot_df = df.pivot_table(index='barcode', columns='name', values=value_col, fill_value=0)
        
        # 2. Filter Top Species (Avoid cluttering the plot with 1000s of species)
        #    Sum columns, take top 15, group others (optional, skipping group for simplicity)
        top_species = pivot_df.sum().nlargest(15).index
        pivot_df = pivot_df[top_species]
        
        barcodes = pivot_df.index.tolist()
        x = np.arange(len(barcodes))

        # 3. Setup X-Axis Labels
        ticks = [list(zip(x, barcodes))]
        self.x_axis.setTicks(ticks)

        # 4. Stacked Bar Logic
        bottom = np.zeros(len(barcodes))
        
        # Apple-like Palette (Pastels)
        colors = [
            (100, 149, 237), (255, 127, 80), (144, 238, 144), (255, 215, 0),
            (221, 160, 221), (32, 178, 170), (240, 128, 128), (135, 206, 250),
            (255, 160, 122), (173, 216, 230), (255, 105, 180), (210, 180, 140)
        ]

        for i, species in enumerate(top_species):
            heights = pivot_df[species].values
            
            # Cyclic color selection
            color = colors[i % len(colors)]
            
            # Create Bar Segment
            bar = pg.BarGraphItem(
                x=x, 
                y0=bottom, 
                height=heights, 
                width=0.6, 
                brush=pg.mkBrush(color), 
                pen=pg.mkPen('w', width=1), # White border for clean stacking
                name=species
            )
            
            self.plot_widget.addItem(bar)
            
            # Increment bottom for next stack
            bottom += heights

# --- Main Window ---
class AbundanceWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # Create the two plot widgets
        self.abs_plot = StackedBarPlotWidget("Absolute Abundance (Top 15)", "Read Count")
        self.rel_plot = StackedBarPlotWidget("Relative Abundance (Top 15)", "Percentage (%)")
        
        self.tabs.addTab(self.abs_plot, "Absolute")
        self.tabs.addTab(self.rel_plot, "Relative")
        
        self.layout.addWidget(self.tabs)
        
        self.loader = None

    def update_data(self, config):
        output_dir = config.get('Paths', 'output_directory')
        # We now look for a CSV, not a PNG
        csv_path = os.path.join(output_dir, "aggregated_results", "abundance_data.csv")
        
        if not os.path.exists(csv_path):
            return

        # Threading Check
        if self.loader is not None and self.loader.isRunning():
            return

        self.loader = AbundanceLoader(csv_path)
        self.loader.data_loaded.connect(self.on_data_loaded)
        self.loader.start()

    @pyqtSlot(pd.DataFrame)
    def on_data_loaded(self, df):
        if df.empty: return
        
        # Expected columns: ['barcode', 'name', 'absolute_abundance', 'relative_abundance']
        # If your CSV has different names, adjust here.
        
        # Update Absolute Plot
        if 'absolute_abundance' in df.columns:
            self.abs_plot.update_plot(df, 'absolute_abundance')
            
        # Update Relative Plot
        if 'relative_abundance' in df.columns:
            self.rel_plot.update_plot(df, 'relative_abundance')