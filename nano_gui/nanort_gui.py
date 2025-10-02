# nano_gui/nanort_gui.py
import sys
import os
import configparser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QListWidget, QStackedWidget, QListWidgetItem,
                             QSplitter, QVBoxLayout)
from PyQt6.QtCore import QTimer, QSize, Qt # <-- FIX IS HERE

# Import the window widgets
from ui_windows.run_preparation import RunPreparationWindow
from ui_windows.basic_stats import BasicStatsWindow
from ui_windows.taxonomy import TaxonomyWindow
from ui_windows.accumulation import AccumulationWindow
from ui_windows.abundance import AbundanceWindow

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NanoRT: Real-Time Analysis Dashboard")
        self.setGeometry(100, 100, 1400, 900)

        # --- Main Layout ---
        self.splitter = QSplitter()
        self.setCentralWidget(self.splitter)

        # --- Left Navigation Menu ---
        self.nav_menu = QListWidget()
        self.nav_menu.setMaximumWidth(200)
        self.splitter.addWidget(self.nav_menu)
        
        # --- Right Content Area (Stacked Widget) ---
        self.stacked_widget = QStackedWidget()
        self.splitter.addWidget(self.stacked_widget)
        
        self.splitter.setSizes([150, 850])

        # --- Create and add windows ---
        self.windows = {
            "Run Preparation": RunPreparationWindow(),
            "Basic Stats": BasicStatsWindow(),
            "Taxonomy": TaxonomyWindow(),
            "Accumulation Plots": AccumulationWindow(),
            "Abundance Plots": AbundanceWindow()
        }
        
        for name, widget in self.windows.items():
            self.stacked_widget.addWidget(widget)
            item = QListWidgetItem(name)
            item.setSizeHint(QSize(0, 30))
            self.nav_menu.addItem(item)

        self.nav_menu.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        
        # --- Real-time update timer ---
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(15 * 1000) # 15 seconds
        self.update_timer.timeout.connect(self.refresh_dashboard_views)
        
        # Initially, only "Run Preparation" is accessible
        for i in range(1, self.nav_menu.count()):
            # Use bitwise AND with the inverted flag to remove the ItemIsEnabled flag
            self.nav_menu.item(i).setFlags(self.nav_menu.item(i).flags() & ~Qt.ItemFlag.ItemIsEnabled)
            
        # Connect the start button of the run prep window to enabling the other tabs
        self.windows["Run Preparation"].start_btn.clicked.connect(self.activate_dashboard)

    def activate_dashboard(self):
        """Enable all dashboard tabs and start the refresh timer."""
        # A small delay to ensure the backend has started
        QTimer.singleShot(1000, self._enable_tabs_and_timer)

    def _enable_tabs_and_timer(self):
        run_prep_window = self.windows["Run Preparation"]
        run_prep_window.log_viewer.appendPlainText("--- Activating dashboard views and starting auto-refresh ---")
        for i in range(1, self.nav_menu.count()):
             # Use bitwise OR to add the ItemIsEnabled flag back
            self.nav_menu.item(i).setFlags(self.nav_menu.item(i).flags() | Qt.ItemFlag.ItemIsEnabled)
        self.update_timer.start()

    def refresh_dashboard_views(self):
        # The UI is in 'nano_gui/', so the config is in the parent directory
        config_path = '../config.ini'
        if not os.path.exists(config_path):
            return
            
        config = configparser.ConfigParser()
        config.read(config_path)

        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'update_data'):
             current_widget.update_data(config)
             log_message = f"Refreshed '{self.nav_menu.currentItem().text()}' view."
             self.windows["Run Preparation"].log_viewer.appendPlainText(log_message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())