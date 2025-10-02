# nano_gui/ui_windows/basic_stats.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class BasicStatsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.label = QLabel("Basic Statistics (coming soon)")
        layout.addWidget(self.label)
    
    def update_data(self, config):
        # TODO: Implement logic to read summary files and update labels
        pass