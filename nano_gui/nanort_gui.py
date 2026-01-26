import sys
import os
import configparser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QListWidget, QStackedWidget, QListWidgetItem,
                             QSplitter, QVBoxLayout, QLabel)
from PyQt6.QtGui import QPixmap 
from PyQt6.QtCore import QTimer, QSize, Qt 

# Import the window widgets
from ui_windows.run_preparation import RunPreparationWindow
from ui_windows.basic_stats import BasicStatsWindow
from ui_windows.taxonomy import TaxonomyWindow
from ui_windows.accumulation import AccumulationWindow
from ui_windows.abundance import AbundanceWindow
from styles import apply_boutique_style
from report_generator import ReportGenerator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetaRT: Real-Time Analysis Dashboard")
        self.setGeometry(100, 100, 1400, 900)

        self.report_worker = None 

        # --- Sidebar Palette ---
        c_very_light_teal = "#F1F4F4"  
        c_dark_teal = "#3c5457"        

        # --- Main Layout ---
        self.splitter = QSplitter()
        self.setCentralWidget(self.splitter)

        # --- Left Side Container (Logo + Menu) ---
        self.left_panel = QWidget()
        self.left_panel.setMaximumWidth(220) 
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)

        # 1. The Logo
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet(f"padding: 20px 0px 10px 0px; background-color: {c_very_light_teal};") 

        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            pixmap = pixmap.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("MetaRT")
            self.logo_label.setStyleSheet(f"""
                font-size: 28px; font-weight: bold; color: {c_dark_teal}; 
                padding: 30px 0px; background-color: {c_very_light_teal};
            """)

        self.left_layout.addWidget(self.logo_label)

        # 2. The Navigation Menu
        self.nav_menu = QListWidget()
        self.nav_menu.setStyleSheet(f"""
            QListWidget {{ border: none; background-color: {c_very_light_teal}; }}
            QListWidget::item {{ color: {c_dark_teal}; }}
            QListWidget::item:selected {{ background-color: {c_dark_teal}; color: white; }}
        """)
        self.left_layout.addWidget(self.nav_menu)
        self.splitter.addWidget(self.left_panel)
        
        # --- Right Content Area ---
        self.stacked_widget = QStackedWidget()
        self.splitter.addWidget(self.stacked_widget)
        self.splitter.setSizes([220, 1180])

        # --- Create Windows ---
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
            item.setSizeHint(QSize(0, 45)) 
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) 
            self.nav_menu.addItem(item)

        self.nav_menu.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        
        # --- Real-time update timer (GUI) ---
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(15 * 1000)
        self.update_timer.timeout.connect(self.refresh_dashboard_views)
        
        # Initially disable tabs
        for i in range(1, self.nav_menu.count()):
            self.nav_menu.item(i).setFlags(self.nav_menu.item(i).flags() & ~Qt.ItemFlag.ItemIsEnabled)
            
        self.windows["Run Preparation"].start_btn.clicked.connect(self.activate_dashboard)

    def activate_dashboard(self):
        """Start GUI refresh and Background Report Generator."""
        QTimer.singleShot(1000, self._enable_tabs_and_timer)
        self.start_report_generator()

    def start_report_generator(self):
        """Initializes background HTML report generator with logging."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
        
        if os.path.exists(config_path):
            config = configparser.ConfigParser()
            config.read(config_path)
            output_dir = config.get('Paths', 'output_directory', fallback=None)
            
            # --- FIX 1: Use 'log_viewer' instead of 'log_output' ---
            log_win = self.windows["Run Preparation"].log_viewer
            
            if output_dir:
                # Force absolute path to avoid confusion
                abs_output_dir = os.path.abspath(output_dir)
                
                log_win.appendPlainText(">>> Initializing Remote Dashboard...")
                log_win.appendPlainText(f"    Target Dir: {abs_output_dir}")

                if self.report_worker and self.report_worker.isRunning():
                    return

                self.report_worker = ReportGenerator(abs_output_dir)
                # CONNECT LOG SIGNAL
                self.report_worker.log_message.connect(self.append_worker_log)
                self.report_worker.start()
            else:
                 log_win.appendPlainText("ERROR: No output directory in config.")

    def append_worker_log(self, text):
        """Slot to receive text from the background thread."""
        # --- FIX 2: Use 'log_viewer' here too ---
        self.windows["Run Preparation"].log_viewer.appendPlainText(text)

    def _enable_tabs_and_timer(self):
        # --- FIX 3: Use 'log_viewer' here too ---
        self.windows["Run Preparation"].log_viewer.appendPlainText("--- Activating GUI views ---")
        
        for i in range(1, self.nav_menu.count()):
            self.nav_menu.item(i).setFlags(self.nav_menu.item(i).flags() | Qt.ItemFlag.ItemIsEnabled)
        self.update_timer.start()

    def refresh_dashboard_views(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
        if not os.path.exists(config_path): return
            
        config = configparser.ConfigParser()
        config.read(config_path)
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'update_data'):
             current_widget.update_data(config)

    def closeEvent(self, event):
        if self.report_worker:
            self.report_worker.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_boutique_style(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())