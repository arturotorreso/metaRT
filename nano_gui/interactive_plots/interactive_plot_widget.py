# nano_gui/interactive_plots/interactive_plot_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

class InteractivePlotWidget(QWidget):
    """Base class for our interactive plot widgets."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget)

        # Basic plot styling
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.getAxis('left').setTextPen('k')
        self.plot_widget.getAxis('bottom').setTextPen('k')

        self.legend = self.plot_widget.addLegend()

    def update_data(self, data_file):
        """This method will be implemented by child classes to load and plot data."""
        raise NotImplementedError