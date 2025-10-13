# nano_gui/ui_windows/run_preparation.py
import configparser
import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QFileDialog, QGroupBox, QPlainTextEdit,
                             QSpinBox, QCheckBox, QTabWidget, QScrollArea, QDoubleSpinBox)
from PyQt6.QtCore import QProcess, pyqtSlot

class RunPreparationWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend_process = None
        self._block_barcode_signals = False  # Flag to prevent signal loops
        self.setupUi()
        self.connect_signals()
        self.load_default_config()

    def setupUi(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.setup_run_config_tab()
        self.setup_pipeline_options_tab()
        self.setup_log_tab()
        
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Analysis")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.stop_btn = QPushButton("Stop Analysis")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        main_layout.addLayout(button_layout)

    def setup_run_config_tab(self):
        """Creates the 'Run & Barcodes' tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        run_group = QGroupBox("Run Configuration")
        run_grid = QGridLayout()
        
        run_grid.addWidget(QLabel("Project Name:"), 0, 0)
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("e.g., my_sample_run")
        run_grid.addWidget(self.project_name_edit, 0, 1, 1, 2)
        
        run_grid.addWidget(QLabel("Input Nanopore Folder:"), 1, 0)
        self.input_dir_edit = QLineEdit()
        run_grid.addWidget(self.input_dir_edit, 1, 1)
        self.browse_input_btn = QPushButton("Browse...")
        run_grid.addWidget(self.browse_input_btn, 1, 2)
        
        run_grid.addWidget(QLabel("Output Directory:"), 2, 0)
        self.output_dir_edit = QLineEdit()
        run_grid.addWidget(self.output_dir_edit, 2, 1)
        self.browse_output_btn = QPushButton("Browse...")
        run_grid.addWidget(self.browse_output_btn, 2, 2)
        
        run_group.setLayout(run_grid)
        layout.addWidget(run_group)
        
        barcode_group = QGroupBox("Barcode Selection")
        barcode_layout = QVBoxLayout()
        
        barcode_text_layout = QHBoxLayout()
        barcode_text_layout.addWidget(QLabel("Enter Barcodes (e.g., 1-5, 8, 12-14):"))
        self.barcode_text_edit = QLineEdit()
        barcode_text_layout.addWidget(self.barcode_text_edit)
        barcode_layout.addLayout(barcode_text_layout)
        
        self.barcode_checkboxes = []
        checkbox_grid = QGridLayout()
        for i in range(24):
            num = i + 1
            checkbox = QCheckBox(f"{num:02d}")
            self.barcode_checkboxes.append(checkbox)
            checkbox_grid.addWidget(checkbox, i // 8, i % 8)
        barcode_layout.addLayout(checkbox_grid)
        
        barcode_group.setLayout(barcode_layout)
        layout.addWidget(barcode_group)
        layout.addStretch()
        
        self.tabs.addTab(tab_widget, "Run & Barcodes")

    def setup_pipeline_options_tab(self):
        """Creates the 'Pipeline Options' tab with a scroll area."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        steps_group = QGroupBox("Workflow Steps")
        steps_layout = QHBoxLayout()
        self.host_depletion_cb = QCheckBox("Host Depletion")
        self.read_qc_cb = QCheckBox("Read QC")
        self.classification_cb = QCheckBox("Kraken2")
        self.mapping_cb = QCheckBox("Mapping")
        self.smart_cb = QCheckBox("SMART")
        steps_layout.addWidget(self.host_depletion_cb)
        steps_layout.addWidget(self.read_qc_cb)
        steps_layout.addWidget(self.classification_cb)
        steps_layout.addWidget(self.mapping_cb)
        steps_layout.addWidget(self.smart_cb)
        steps_group.setLayout(steps_layout)
        layout.addWidget(steps_group)

        db_group = QGroupBox("Database Paths")
        db_grid = QGridLayout()
        self.db_widgets = {}
        db_params = ["host_reference", "kraken_db", "taxonomy_dir", "refseq_db", "smart_db"]
        for i, param in enumerate(db_params):
            db_grid.addWidget(QLabel(f"{param}:"), i, 0)
            line_edit = QLineEdit()
            browse_btn = QPushButton("Browse...")
            browse_btn.clicked.connect(lambda _, le=line_edit, p=param: self.browse_path(le, p))
            db_grid.addWidget(line_edit, i, 1)
            db_grid.addWidget(browse_btn, i, 2)
            self.db_widgets[param] = line_edit
        db_group.setLayout(db_grid)
        layout.addWidget(db_group)
        
        params_layout = QHBoxLayout()
        
        qc_group = QGroupBox("QC Parameters (qc_opts)")
        qc_grid = QGridLayout()
        self.qc_widgets = {
            "min_mean_q": QSpinBox(), "min_length": QSpinBox(),
            "trim5": QCheckBox("Trim 5'"), "trim3": QCheckBox("Trim 3'"),
            "window_size": QSpinBox(), "cut_quality": QSpinBox(),
            "perc_low_qual": QSpinBox(), "min_base_q": QSpinBox(),
            "low_complexity": QCheckBox("Low Complexity Filter"),
            "entropy": QDoubleSpinBox(), "entropy_window": QSpinBox(),
            "entropy_kmer": QSpinBox(), "disable_adapters": QCheckBox("Disable Adapters")
        }
        self.qc_widgets["min_length"].setRange(0, 100000)
        self.qc_widgets["min_length"].setValue(1000)
        self.qc_widgets["entropy"].setDecimals(1)
        for i, (name, widget) in enumerate(self.qc_widgets.items()):
            label = name.replace('_', ' ').title() if not isinstance(widget, QCheckBox) else ""
            qc_grid.addWidget(QLabel(label), i, 0)
            qc_grid.addWidget(widget, i, 1)
        qc_group.setLayout(qc_grid)
        params_layout.addWidget(qc_group)
        
        other_params_vbox = QVBoxLayout()
        
        kraken_group = QGroupBox("Kraken Parameters (kraken_opts)")
        kraken_grid = QGridLayout()
        self.kraken_widgets = {
            "confidence": QDoubleSpinBox(),
            "memory_mapping": QCheckBox("Memory Mapping"),
            "min_base_q": QSpinBox(),
            "min_hit_groups": QSpinBox()
        }
        self.kraken_widgets["confidence"].setDecimals(2)
        for i, (name, widget) in enumerate(self.kraken_widgets.items()):
            label = name.replace('_', ' ').title() if not isinstance(widget, QCheckBox) else ""
            kraken_grid.addWidget(QLabel(label), i, 0)
            kraken_grid.addWidget(widget, i, 1)
        kraken_group.setLayout(kraken_grid)
        other_params_vbox.addWidget(kraken_group)

        mapping_group = QGroupBox("Mapping Parameters (mapping_opts)")
        mapping_grid = QGridLayout()
        self.mapping_widgets = {"secondary_aligns": QSpinBox()}
        for i, (name, widget) in enumerate(self.mapping_widgets.items()):
            mapping_grid.addWidget(QLabel(name.replace('_', ' ').title()), i, 0)
            mapping_grid.addWidget(widget, i, 1)
        mapping_group.setLayout(mapping_grid)
        other_params_vbox.addWidget(mapping_group)
        other_params_vbox.addStretch()

        params_layout.addLayout(other_params_vbox)
        layout.addLayout(params_layout)
        
        scroll_area.setWidget(tab_widget)
        self.tabs.addTab(scroll_area, "Pipeline Options")

    def setup_log_tab(self):
        """Creates the 'Backend Log' tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("background-color: #2b2b2b; color: #f0f0f0; font-family: 'Courier New';")
        layout.addWidget(self.log_viewer)
        self.tabs.addTab(tab_widget, "Backend Log")
        
    def connect_signals(self):
        self.start_btn.clicked.connect(self.start_analysis)
        self.stop_btn.clicked.connect(self.stop_analysis)
        self.browse_input_btn.clicked.connect(lambda: self.browse_directory(self.input_dir_edit))
        self.browse_output_btn.clicked.connect(lambda: self.browse_directory(self.output_dir_edit))
        self.project_name_edit.textChanged.connect(self.update_paths_from_project)
        self.barcode_text_edit.textChanged.connect(self.update_checkboxes_from_text)
        for checkbox in self.barcode_checkboxes:
            checkbox.stateChanged.connect(self.update_text_from_checkboxes)

    def load_default_config(self):
        """Loads default values from a sample config into the UI."""
        config = self.get_sample_config()
        
        # Populate Paths
        self.input_dir_edit.setText(config.get('Paths', 'fastq_directory', fallback=""))
        self.output_dir_edit.setText(config.get('Paths', 'output_directory', fallback=""))
        
        # Populate Barcodes
        self.barcode_text_edit.setText(config.get('Settings', 'barcodes', fallback=""))
        
        # Populate WorkflowSteps
        self.host_depletion_cb.setChecked(config.getboolean('WorkflowSteps', 'run_host_depletion'))
        self.read_qc_cb.setChecked(config.getboolean('WorkflowSteps', 'run_read_qc'))
        self.classification_cb.setChecked(config.getboolean('WorkflowSteps', 'run_classification'))
        self.mapping_cb.setChecked(config.getboolean('WorkflowSteps', 'run_mapping'))
        self.smart_cb.setChecked(config.getboolean('WorkflowSteps', 'run_smart'))
        
        # Populate DatabasePaths
        for name, widget in self.db_widgets.items():
            widget.setText(config.get('DatabasePaths', name, fallback=""))

        # Populate QcParams
        for name, widget in self.qc_widgets.items():
            if isinstance(widget, QCheckBox):
                widget.setChecked(config.getboolean('QcParams', name))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(config.getfloat('QcParams', name))
            else:
                widget.setValue(config.getint('QcParams', name))

        # Populate KrakenParams
        for name, widget in self.kraken_widgets.items():
            if isinstance(widget, QCheckBox):
                widget.setChecked(config.getboolean('KrakenParams', name))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(config.getfloat('KrakenParams', name))
            else:
                widget.setValue(config.getint('KrakenParams', name))

        # Populate MappingParams
        for name, widget in self.mapping_widgets.items():
            widget.setValue(config.getint('MappingParams', name))


    def get_sample_config(self):
        """Provides a complete, default configuration."""
        config = configparser.ConfigParser()
        config.read_string("""
[Paths]
fastq_directory = /var/lib/minknow/data/
output_directory = /mnt/Drive20T/
nextflow_script = ../nextflow_pipeline/main.nf

[Settings]
batch_interval_seconds = 60
processed_files_log = processed_files.log
barcodes = 1-6

[WorkflowSteps]
run_host_depletion = false
run_read_qc = true
run_classification = true
run_kraken = true
run_mapping = false
run_smart = false

[DatabasePaths]
host_reference = /mnt/Drive20T/db/human_genome/GCF_000001405.40_GRCh38.p14_genomic.fna
kraken_db = /mnt/Drive20T/db/kraken2_standard_pluspf
taxonomy_dir = /mnt/Drive20T/scripts/metaRT/scripts/kraken2/data
refseq_db = /mnt/Drive20T/db/refseq/target.fna.gz.mm2idx
smart_db = /mnt/Drive20T/smart/database/test/python_wrapped/

[HostDepletionParams]
keep_bam = false

[QcParams]
min_mean_q = 10
min_length = 75
trim5 = false
trim3 = false
window_size = 10
cut_quality = 10
perc_low_qual = 40
min_base_q = 10
low_complexity = true
entropy = 0.6
entropy_window = 50
entropy_kmer = 5
disable_adapters = false

[KrakenParams]
confidence = 0
memory_mapping = true
min_base_q = 0
min_hit_groups = 2

[MappingParams]
secondary_aligns = 5
        """)
        return config

    # --- SLOTS for UI interaction ---

    @pyqtSlot(str)
    def update_paths_from_project(self, text):
        """Automatically update input and output paths based on project name."""
        if text:
            self.input_dir_edit.setText(os.path.join("/var/lib/minknow/data", text))
            self.output_dir_edit.setText(os.path.join("/mnt/Drive20T", text))
        else:
            self.input_dir_edit.clear()
            self.output_dir_edit.clear()

    @pyqtSlot(str)
    def update_checkboxes_from_text(self, text):
        if self._block_barcode_signals: return
        self._block_barcode_signals = True
        
        selected_indices = set()
        try:
            for part in text.split(','):
                part = part.strip()
                if not part: continue
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    for i in range(start, end + 1):
                        if 1 <= i <= 24: selected_indices.add(i - 1)
                else:
                    i = int(part)
                    if 1 <= i <= 24: selected_indices.add(i - 1)
        except ValueError:
            pass # Ignore errors during typing

        for i, checkbox in enumerate(self.barcode_checkboxes):
            checkbox.setChecked(i in selected_indices)
        
        self._block_barcode_signals = False

    @pyqtSlot(int)
    def update_text_from_checkboxes(self, state):
        if self._block_barcode_signals: return
        self._block_barcode_signals = True

        selected = [i + 1 for i, cb in enumerate(self.barcode_checkboxes) if cb.isChecked()]
        
        if not selected:
            self.barcode_text_edit.setText("")
        else:
            # Create a compact range string (e.g., "1-3, 5")
            ranges = []
            start_of_range = end_of_range = selected[0]
            for i in range(1, len(selected)):
                if selected[i] == end_of_range + 1:
                    end_of_range = selected[i]
                else:
                    ranges.append(str(start_of_range) if start_of_range == end_of_range else f"{start_of_range}-{end_of_range}")
                    start_of_range = end_of_range = selected[i]
            ranges.append(str(start_of_range) if start_of_range == end_of_range else f"{start_of_range}-{end_of_range}")
            self.barcode_text_edit.setText(", ".join(ranges))
        
        self._block_barcode_signals = False

    def browse_directory(self, line_edit):
        dir_name = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_name: line_edit.setText(dir_name)

    def browse_path(self, line_edit, param_name):
        """Generic browser for files or directories."""
        if "dir" in param_name:
            path = QFileDialog.getExistingDirectory(self, f"Select Directory for {param_name}")
        else:
            path, _ = QFileDialog.getOpenFileName(self, f"Select File for {param_name}")
        if path:
            line_edit.setText(path)
    
    def write_config(self):
        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.realpath(__file__))
        
        # Section [Paths]
        nextflow_script_path = os.path.abspath(os.path.join(current_dir, '..', '..','nextflow_pipeline', 'main.nf'))
        config['Paths'] = {
            'fastq_directory': self.input_dir_edit.text(),
            'output_directory': self.output_dir_edit.text(),
            'nextflow_script': nextflow_script_path
        }

        # Section [Settings]
        barcodes_text = self.barcode_text_edit.text()
        parsed_barcodes = []
        for part in barcodes_text.split(','):
            part = part.strip()
            if not part: continue
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    parsed_barcodes.extend([f"barcode{i:02d}" for i in range(start, end + 1)])
                except ValueError: pass
            else:
                try:
                    parsed_barcodes.append(f"barcode{int(part):02d}")
                except ValueError: pass
        
        # config['Settings'] = {
        #     'batch_interval_seconds': self.batch_interval_spin.value(),
        #     'processed_files_log': 'processed_files.log',
        #     'barcodes': ", ".join(parsed_barcodes)
        # }

        ######## TODO: Hard coded, need to update #######
        config['Settings'] = {
            'batch_interval_seconds': '10', # Changed from self.batch_interval_spin.value()
            'processed_files_log': 'processed_files.log',
            'barcodes': ", ".join(parsed_barcodes)
        }        # Section [WorkflowSteps]
        config['WorkflowSteps'] = {
            'run_host_depletion': str(self.host_depletion_cb.isChecked()).lower(),
            'run_read_qc': str(self.read_qc_cb.isChecked()).lower(),
            'run_classification': str(self.classification_cb.isChecked()).lower(),
            'run_kraken': str(self.classification_cb.isChecked()).lower(),
            'run_mapping': str(self.mapping_cb.isChecked()).lower(),
            'run_smart': str(self.smart_cb.isChecked()).lower()
        }
        
        # Section [DatabasePaths]
        config['DatabasePaths'] = {name: widget.text() for name, widget in self.db_widgets.items()}
        
        # Sections for Tool Params
        config['HostDepletionParams'] = {'keep_bam': 'false'} # Currently static
        config['QcParams'] = {name: str(w.isChecked()).lower() if isinstance(w, QCheckBox) else str(w.value()) for name, w in self.qc_widgets.items()}
        config['KrakenParams'] = {name: str(w.isChecked()).lower() if isinstance(w, QCheckBox) else str(w.value()) for name, w in self.kraken_widgets.items()}
        config['MappingParams'] = {name: str(w.value()) for name, w in self.mapping_widgets.items()}

        config_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'config.ini'))
        with open(config_path, 'w') as configfile:
            config.write(configfile)
        self.log_viewer.appendPlainText(f"Configuration file '{config_path}' saved.")
        return True

    def start_analysis(self):
        self.write_config()
        self.log_viewer.clear()
        self.log_viewer.appendPlainText("Starting backend process...")
        self.tabs.setCurrentIndex(2)

        self.backend_process = QProcess(self)
        self.backend_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.backend_process.readyReadStandardOutput.connect(self.handle_stdout)
        self.backend_process.finished.connect(self.process_finished)

        current_dir = os.path.dirname(os.path.realpath(__file__))
        backend_script_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'nanort_backend.py'))
        config_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'config.ini'))

        self.backend_process.start(sys.executable, [backend_script_path, "-c", config_path])
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.tabs.widget(0).setEnabled(False)
        self.tabs.widget(1).setEnabled(False)

    def handle_stdout(self):
        data = self.backend_process.readAllStandardOutput()
        self.log_viewer.appendPlainText(str(data, 'utf-8').strip())

    def stop_analysis(self):
        if self.backend_process and self.backend_process.state() == QProcess.ProcessState.Running:
            self.log_viewer.appendPlainText("\n--- Sending termination signal to backend ---")
            self.backend_process.terminate()
            self.backend_process.waitForFinished(3000)

    def process_finished(self):
        self.log_viewer.appendPlainText("--- Backend process has finished ---")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.tabs.widget(0).setEnabled(True)
        self.tabs.widget(1).setEnabled(True)
        self.backend_process = None