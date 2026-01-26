# nano_gui/styles.py

def apply_boutique_style(app):
    """
    Applies the Chromologic-inspired palette to the entire application.
    Includes a Base64 encoded checkmark to ensure visibility on all platforms.
    """
    
    # --- Chromologic Palette ---
    c_dark_teal = "#3c5457"    # Dark Teal
    c_light_teal = "#bbc9c9"   # Light Grey-Teal
    c_very_light_teal = "#F1F4F4"
    c_white = "#ffffff"        # White
    c_stop_red = "#A94442"     # Muted Red

    # Robust SVG Checkmark (White check) encoded for Qt
    # This prevents the "invisible checkmark" bug
    checkmark_svg = (
        "url('data:image/svg+xml;charset=utf-8,"
        "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 "
        "viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22white%22 stroke-width=%224%22 "
        "stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E"
        "%3Cpolyline points=%2220 6 9 17 4 12%22/%3E%3C/svg%3E')"
    )

    stylesheet = f"""
    /* --- Main Window & General --- */
    QMainWindow, QDialog, QWidget {{
        background-color: {c_light_teal};
        color: {c_dark_teal};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 13px;
    }}

    /* --- Inputs (White Background) --- */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {c_white};
        color: black;
        border: 1px solid {c_dark_teal};
        border-radius: 4px;
        padding: 5px;
        selection-background-color: {c_dark_teal};
        selection-color: {c_white};
    }}

    /* --- Checkboxes (The Fix) --- */
    QCheckBox {{
        spacing: 8px;
        color: {c_dark_teal};
        font-weight: 500;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        background-color: {c_white};
        border: 2px solid {c_dark_teal};
        border-radius: 4px;
    }}
    QCheckBox::indicator:hover {{
        border-color: #007AFF; /* Blue highlight on hover */
    }}
    QCheckBox::indicator:checked {{
        background-color: {c_dark_teal}; /* Fills the square with Teal */
        border: 2px solid {c_dark_teal};
        image: {checkmark_svg}; /* Overlays the white checkmark */
    }}

    /* --- Group Boxes --- */
    QGroupBox {{
        border: 2px solid {c_dark_teal};
        border-radius: 8px;
        margin-top: 1.5em;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        color: {c_dark_teal};
    }}

    /* --- Buttons --- */
    QPushButton {{
        background-color: {c_white};
        color: {c_dark_teal};
        border: 1px solid {c_dark_teal};
        border-radius: 6px;
        padding: 6px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: #e0e6e6;
    }}
    QPushButton:pressed {{
        background-color: {c_dark_teal};
        color: {c_white};
    }}
    
    /* Specific Button Overrides */
    QPushButton#start_btn {{
        background-color: {c_dark_teal};
        color: {c_white};
        border: none;
    }}
    QPushButton#start_btn:hover {{
        background-color: #2a3c3e;
    }}
    QPushButton#stop_btn {{
        background-color: {c_stop_red};
        color: {c_white};
        border: none;
    }}
    QPushButton#stop_btn:hover {{
        background-color: #8a2a2a;
    }}

    /* --- Sidebar & Tabs --- */
    QListWidget, QTabWidget::pane {{
        background-color: {c_light_teal};
        border: none;
        outline: none;
    }}
    QListWidget::item:selected, QTabBar::tab:selected {{
        background-color: {c_dark_teal};
        color: {c_white};
    }}
    QTabBar::tab {{
        background: #99a8a8;
        color: {c_dark_teal};
        padding: 8px 20px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }}
    """
    app.setStyleSheet(stylesheet)