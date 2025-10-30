import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
# This import brings in the widget with all the new interactive features
from cumulative_widget import CumulativePlot

class TestWindow(QMainWindow):
    """A simple window to host and test the CumulativePlot widget."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cumulative Plot Widget Test")
        self.setGeometry(100, 100, 800, 600)

        # Instantiate the widget we want to test
        self.cumulative_plot_widget = CumulativePlot()
        
        # Set it as the central widget of our test window
        self.setCentralWidget(self.cumulative_plot_widget)

        # Load the mock data into the widget
        self.load_test_data()

    def load_test_data(self):
        """Finds and loads the mock CSV data into the widget."""
        # The test data is in a subdirectory relative to this script
        mock_data_path = os.path.join(os.path.dirname(__file__), 'test_data', 'mock_cumulative_data.csv')

        if not os.path.exists(mock_data_path):
            print(f"Error: Mock data file not found at '{mock_data_path}'")
            return
            
        print(f"Loading data from: {mock_data_path}")
        self.cumulative_plot_widget.update_data(mock_data_path)

if __name__ == '__main__':
    # Standard PyQt application setup
    app = QApplication(sys.argv)
    test_window = TestWindow()
    test_window.show()
    sys.exit(app.exec())

