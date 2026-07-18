from __future__ import annotations

import sys
import re
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from .analysis import average_sweeps, baseline_subtract, fft_area
from .display import current_sweep_index
from .events import detect_threshold_crossings
from .field_potential import FieldPotentialSettings, analyze_field_potential, result_to_row, preprocess_sweep
from .loaders import LoaderError, load_any
from .state import ZPhysState


@dataclass
class DisplayTrace:
    """A trace currently shown on the graph and eligible for analysis."""

    x: np.ndarray
    y: np.ndarray
    series_name: str = ""
    sweep_index: int = 0
    display_name: str = ""
    sampling_interval: float | None = None
    units: str = ""
    source: str = "displayed"


class NoWheelDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """QDoubleSpinBox that ignores trackpad/mouse-wheel changes."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSpinBox(QtWidgets.QSpinBox):
    """QSpinBox that ignores trackpad/mouse-wheel changes."""

    def wheelEvent(self, event):
        event.ignore()





class VerticalOnlyScrollArea(QtWidgets.QScrollArea):
    """Vertical-only QScrollArea whose content tracks the viewport width."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        widget = self.widget()
        if widget is not None:
            widget.setFixedWidth(max(1, self.viewport().width()))

    def wheelEvent(self, event):
        angle_delta = event.angleDelta()
        pixel_delta = event.pixelDelta()

        dy = angle_delta.y() if not angle_delta.isNull() else pixel_delta.y()
        if dy == 0:
            event.accept()
            return

        bar = self.verticalScrollBar()
        if not pixel_delta.isNull() and pixel_delta.y() != 0:
            step = -pixel_delta.y()
        else:
            step = int(-dy / 120 * bar.singleStep() * 3)

        bar.setValue(bar.value() + step)
        event.accept()

def _primary_button_style() -> str:
    """Return a readable primary-button style for the Load File button."""
    return """
        QPushButton {
            background-color: #2563eb;
            color: white;
            border: 1px solid #1d4ed8;
            border-radius: 6px;
            padding: 6px 10px;
            font-weight: 600;
        }
        QPushButton:hover { background-color: #1d4ed8; }
        QPushButton:pressed { background-color: #1e40af; }
    """


class CollapsibleBox(QtWidgets.QGroupBox):
    """Simple checkable/collapsible group box."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)
        self._content = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addWidget(self._content)
        self._content.setVisible(False)
        self.toggled.connect(self._content.setVisible)

    def content_layout(self):
        return self._content_layout


class MainWindow(QtWidgets.QMainWindow):
    """PySide6/PyQtGraph version of the Igor JT_Controls panel."""

    def __init__(self) -> None:
        super().__init__()
        self.state = ZPhysState()
        self._available_series = []
        self._display_mode = "single"
        self._displayed_traces: list[DisplayTrace] = []
        self._range_traces: list[DisplayTrace] = []
        self._baseline_enabled_by_trace_key: dict[tuple[str, int], bool] = {}
        self._detection_marker_items: list[object] = []
        self._stimulus_right_axis_view = None
        self._stimulus_right_axis_curve = None
        self._stimulus_right_axis_resize_slot = None
        self._selected_stimulus_series_name = None
        self._detection_windows: list[object] = []
        self._last_detection_rows: list[dict[str, float | int | str]] = []
        self._last_detection_arrays: dict[str, np.ndarray] = {}
        self._last_fp_rows: list[dict] = []
        self._fp_marker_items: list[object] = []

        self.setWindowTitle("zPhys Python")
        self.resize(1360, 820)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QHBoxLayout(central)

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        outer.addWidget(main_splitter)

        controls_container = QtWidgets.QWidget()
        controls_container.setMinimumWidth(360)
        controls_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        controls_layout = QtWidgets.QVBoxLayout(controls_container)
        main_splitter.addWidget(controls_container)

        plot_and_results = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        main_splitter.addWidget(plot_and_results)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setSizes([455, 905])

        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Signal")
        try:
            self.plot.scene().sigMouseClicked.connect(self._plot_mouse_clicked)
        except Exception:
            pass
        plot_and_results.addWidget(self.plot)

        results_box = QtWidgets.QWidget()
        results_layout = QtWidgets.QVBoxLayout(results_box)
        results_layout.setContentsMargins(0, 4, 0, 0)

        results_header = QtWidgets.QHBoxLayout()
        results_header.addWidget(QtWidgets.QLabel("<b>Results / messages</b>"))
        export_button = QtWidgets.QPushButton("Export Detection CSV")
        export_button.clicked.connect(self.export_detection_csv)
        results_header.addWidget(export_button)
        clear_results_button = QtWidgets.QPushButton("Clear Detection")
        clear_results_button.clicked.connect(self.clear_detection_results)
        results_header.addWidget(clear_results_button)
        results_layout.addLayout(results_header)

        self.results_summary = QtWidgets.QLabel("No detections yet.")
        self.results_summary.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        results_layout.addWidget(self.results_summary)

        self.results_tabs = QtWidgets.QTabWidget()
        results_layout.addWidget(self.results_tabs)

        self.detection_results_tab = QtWidgets.QWidget()
        detection_results_layout = QtWidgets.QVBoxLayout(self.detection_results_tab)
        detection_results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_table = QtWidgets.QTableWidget(0, 16)
        self.results_table.setHorizontalHeaderLabels(
            [
                "source", "series", "sweep", "window", "event", "event_in_window",
                "time_s", "time_from_win_start_s", "isi_s", "amplitude",
                "crossing_time_s", "crossing_from_win_start_s", "first_in_window",
                "direction", "win_start", "win_end",
            ]
        )
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        detection_results_layout.addWidget(self.results_table)
        self.results_tabs.addTab(self.detection_results_tab, "Detection")

        self.fp_results_tab = QtWidgets.QWidget()
        fp_results_layout = QtWidgets.QVBoxLayout(self.fp_results_tab)
        fp_results_layout.setContentsMargins(0, 0, 0, 0)
        self.fp_results_table = QtWidgets.QTableWidget(0, 14)
        self.fp_results_table.setHorizontalHeaderLabels([
            "source", "sweep", "stim_to_peak_s", "fp_latency_s", "fp_amplitude", "fp_length_s",
            "onset_time_s", "onset_y", "peak_time_s", "peak_y", "trough_time_s", "trough_y",
            "return_time_s", "status"
        ])
        self.fp_results_table.horizontalHeader().setStretchLastSection(True)
        self.fp_results_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.fp_results_table.cellDoubleClicked.connect(lambda r, c: self.fp_show_result_row(r))
        fp_results_layout.addWidget(self.fp_results_table)
        self.results_tabs.addTab(self.fp_results_tab, "Field Potential")

        plot_and_results.addWidget(results_box)
        plot_and_results.setSizes([570, 250])

        self._threshold_idle_pen = pg.mkPen("r", width=5)
        self._threshold_active_pen = pg.mkPen("y", width=5)
        self.threshold_line = pg.InfiniteLine(
            angle=0,
            movable=True,
            pen=self._threshold_idle_pen,
        )
        try:
            self.threshold_line.setHoverPen(self._threshold_active_pen)
        except Exception:
            pass
        self.threshold_line.setVisible(False)
        self.threshold_line.sigDragged.connect(self._threshold_line_moved)
        try:
            self.threshold_line.sigPositionChangeFinished.connect(self._threshold_line_released)
        except Exception:
            pass

        title = QtWidgets.QLabel("<b>Trapani Lab zPhys analysis</b>")
        controls_layout.addWidget(title)

        top_group = QtWidgets.QFrame()
        top_layout = QtWidgets.QGridLayout(top_group)
        top_layout.setContentsMargins(4, 4, 4, 4)
        top_layout.setHorizontalSpacing(6)
        top_layout.setVerticalSpacing(3)
        top_layout.setColumnStretch(5, 1)

        self.load_button = QtWidgets.QPushButton("Load File")
        self.load_button.clicked.connect(self.load_file)
        self.load_button.setStyleSheet(_primary_button_style())
        self.load_button.setMinimumHeight(32)
        self.load_button.setToolTip("Open CSV, ABF, IBW, or SutterPatch/Igor PXP.")
        top_layout.addWidget(self.load_button, 0, 0, 1, 6)

        top_layout.addWidget(QtWidgets.QLabel("Signal"), 1, 0)
        self.signal_combo = QtWidgets.QComboBox()
        self.signal_combo.addItem("All", None)
        self.signal_combo.setToolTip("Signals are populated from the loaded file; files with S3/S4/etc. will list those signals when metadata is available.")
        self.signal_combo.currentTextChanged.connect(self._signal_filter_changed)
        top_layout.addWidget(self.signal_combo, 1, 1)

        top_layout.addWidget(QtWidgets.QLabel("Series"), 2, 0)
        self.series_combo = QtWidgets.QComboBox()
        self.series_combo.currentIndexChanged.connect(self._series_selection_changed)
        self.series_combo.setMinimumWidth(220)
        self.series_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.series_combo.setMinimumContentsLength(24)
        try:
            self.series_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        except Exception:
            pass
        top_layout.addWidget(self.series_combo, 2, 1, 1, 5)

        top_layout.addWidget(QtWidgets.QLabel("Sweep"), 1, 2)
        self.sweep_spin = NoWheelSpinBox()
        self.sweep_spin.setRange(1, 1)
        self.sweep_spin.valueChanged.connect(self.update_plot)
        top_layout.addWidget(self.sweep_spin, 1, 3)

        prev_button = QtWidgets.QPushButton("◀")
        prev_button.clicked.connect(self.prev_sweep)
        prev_button.setToolTip("Previous sweep")
        prev_button.setMinimumWidth(36)
        top_layout.addWidget(prev_button, 1, 4)

        next_button = QtWidgets.QPushButton("▶")
        next_button.clicked.connect(self.next_sweep)
        next_button.setToolTip("Next sweep")
        next_button.setMinimumWidth(36)
        top_layout.addWidget(next_button, 1, 5)

        controls_layout.addWidget(top_group)

        common_actions_group = QtWidgets.QGroupBox("Common actions")
        common_actions_layout = QtWidgets.QGridLayout(common_actions_group)
        common_actions_layout.setContentsMargins(8, 6, 8, 6)
        common_actions_layout.setHorizontalSpacing(6)
        common_actions_layout.setVerticalSpacing(3)
        common_actions_layout.setColumnStretch(0, 1)
        common_actions_layout.setColumnStretch(1, 1)
        common_actions_layout.setColumnStretch(2, 1)

        autoscale_main_button = QtWidgets.QPushButton("Autoscale")
        autoscale_main_button.clicked.connect(self.autoscale_displayed_traces)
        autoscale_main_button.setToolTip("Autoscale the current displayed traces.")
        common_actions_layout.addWidget(autoscale_main_button, 0, 0)

        baseline_main_button = QtWidgets.QPushButton("Baseline")
        baseline_main_button.clicked.connect(self.baseline_subtract_scope)
        baseline_main_button.setToolTip("Baseline subtract the current displayed trace(s), or selected sweeps when all-series scope is active.")
        common_actions_layout.addWidget(baseline_main_button, 0, 1)

        overlay_main_button = QtWidgets.QPushButton("Overlay")
        overlay_main_button.clicked.connect(self.overlay_all_sweeps)
        overlay_main_button.setToolTip("Display all selected sweeps overlaid for the current series.")
        common_actions_layout.addWidget(overlay_main_button, 0, 2)

        self.baseline_persist_checkbox = QtWidgets.QCheckBox("Keep baseline")
        self.baseline_persist_checkbox.setChecked(True)
        self.baseline_persist_checkbox.setToolTip("Keep baseline subtraction when changing sweeps.")
        common_actions_layout.addWidget(self.baseline_persist_checkbox, 1, 0)

        self.baseline_all_checkbox = QtWidgets.QCheckBox("All selected")
        self.baseline_all_checkbox.setChecked(True)
        self.baseline_all_checkbox.setToolTip("For selected-sweeps analysis scope, apply baseline subtraction to all selected sweeps.")
        common_actions_layout.addWidget(self.baseline_all_checkbox, 1, 1, 1, 2)

        controls_layout.addWidget(common_actions_group)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        controls_layout.addWidget(self.tabs, stretch=1)

        self.file_tab = QtWidgets.QWidget()
        self.detect_events_tab = QtWidgets.QWidget()
        self.field_potential_tab = QtWidgets.QWidget()
        self.analysis_tab = QtWidgets.QWidget()
        self.display_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.file_tab, "File")
        self.tabs.addTab(self.detect_events_tab, "Detect Events")
        self.tabs.addTab(self.field_potential_tab, "Field Potential")
        self.tabs.addTab(self.analysis_tab, "Analysis")
        self.tabs.addTab(self.display_tab, "Display")

        self._build_file_tab()
        self._build_analysis_tab()
        self._build_field_potential_tab()
        self._build_display_tab()

    def _make_scrollable_tab(self, tab: QtWidgets.QWidget) -> QtWidgets.QVBoxLayout:
        """Create a vertical-only scroll area whose content fills the panel width."""
        outer = QtWidgets.QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = VerticalOnlyScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        content = QtWidgets.QWidget()
        content.setMinimumWidth(0)
        content.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return layout

    def _build_file_tab(self) -> None:
        layout = self._make_scrollable_tab(self.file_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        file_note = QtWidgets.QLabel("Load CSV, ABF, IBW, or SutterPatch/Igor PXP from the blue Load File button above.")
        file_note.setWordWrap(True)
        layout.addWidget(file_note)

        file_button_row = QtWidgets.QHBoxLayout()
        metadata_button = QtWidgets.QPushButton("Metadata")
        metadata_button.clicked.connect(self.show_metadata)
        metadata_button.setToolTip("Show metadata and loader details for the current file.")
        file_button_row.addWidget(metadata_button)

        storage_button = QtWidgets.QPushButton("Data Location")
        storage_button.clicked.connect(self.show_data_storage)
        storage_button.setToolTip("Explain where the loaded series, sweeps, results, and arrays live in memory.")
        file_button_row.addWidget(storage_button)
        layout.addLayout(file_button_row)

        file_tools_help = QtWidgets.QLabel(
            "Metadata shows file/loader details. Data storage explains the Python objects used for loaded traces and analysis results."
        )
        file_tools_help.setWordWrap(True)
        layout.addWidget(file_tools_help)

        self.file_tools_output = QtWidgets.QPlainTextEdit()
        self.file_tools_output.setReadOnly(True)
        self.file_tools_output.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self.file_tools_output.setPlaceholderText("Metadata and data-storage details will appear here.")
        self.file_tools_output.setMinimumHeight(160)
        layout.addWidget(self.file_tools_output)

        self.info_label = QtWidgets.QLabel("No file loaded")
        self.info_label.setWordWrap(True)
        self.info_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.info_label.setToolTip("Loaded-file status and summary.")
        layout.addWidget(self.info_label)

        layout.addStretch()

    def _build_analysis_tab(self) -> None:
        detect_outer_layout = self._make_scrollable_tab(self.detect_events_tab)
        outer_layout = self._make_scrollable_tab(self.analysis_tab)

        shared_group = QtWidgets.QGroupBox("Detection setup")
        shared_layout = QtWidgets.QVBoxLayout(shared_group)
        shared_layout.setContentsMargins(8, 6, 8, 6)
        shared_layout.setSpacing(4)

        scope_label = QtWidgets.QLabel("Analyze source:")
        shared_layout.addWidget(scope_label)

        scope_row = QtWidgets.QHBoxLayout()
        self.analyze_displayed_radio = QtWidgets.QRadioButton("Displayed")
        self.analyze_all_radio = QtWidgets.QRadioButton("Selected sweeps")
        self.analyze_all_radio.setToolTip("Analyze the selected sweeps from the currently selected series.")
        self.analyze_displayed_radio.setChecked(True)
        scope_row.addWidget(self.analyze_displayed_radio)
        scope_row.addWidget(self.analyze_all_radio)
        shared_layout.addLayout(scope_row)

        self.sweep_selection_edit = QtWidgets.QLineEdit("")
        self.sweep_selection_edit.setPlaceholderText("sweeps: blank=all, 1-5,8")
        self.sweep_selection_edit.setToolTip("Selected sweeps for all-series detection and concatenation.")
        shared_layout.addWidget(self.sweep_selection_edit)

        self.use_windows_checkbox = QtWidgets.QCheckBox("Restrict to windows")
        self.use_windows_checkbox.setChecked(False)
        self.use_windows_checkbox.setToolTip("Restrict detection to the active detection windows.")
        shared_layout.addWidget(self.use_windows_checkbox)

        self.window_summary = QtWidgets.QLabel("No windows. Detection uses full trace.")
        self.window_summary.setWordWrap(True)
        self.window_summary.setMaximumHeight(44)
        self.window_summary.setToolTip("Current detection-window summary.")
        shared_layout.addWidget(self.window_summary)

        quick_detect_group = QtWidgets.QGroupBox("Quick detect")
        quick_detect_layout = QtWidgets.QHBoxLayout(quick_detect_group)
        quick_detect_layout.setContentsMargins(8, 6, 8, 6)
        find_top_button = QtWidgets.QPushButton("Find Spikes / Events")
        find_top_button.clicked.connect(self.find_spikes)
        find_top_button.setMinimumHeight(32)
        find_top_button.setToolTip("Run detection using the current threshold, source, and window settings.")
        quick_detect_layout.addWidget(find_top_button)
        self.quick_threshold_readout = QtWidgets.QLabel("Move threshold line, then click Find.")
        self.quick_threshold_readout.setWordWrap(True)
        quick_detect_layout.addWidget(self.quick_threshold_readout, stretch=1)
        detect_outer_layout.addWidget(quick_detect_group)

        self.detection_subtabs = QtWidgets.QTabWidget()
        detect_outer_layout.addWidget(self.detection_subtabs)

        self.detect_subtab = QtWidgets.QWidget()
        self.windows_subtab = QtWidgets.QWidget()
        self.detection_subtabs.addTab(self.detect_subtab, "Detect")
        self.detection_subtabs.addTab(self.windows_subtab, "Windows")

        layout = QtWidgets.QVBoxLayout(self.detect_subtab)
        windows_layout_tab = QtWidgets.QVBoxLayout(self.windows_subtab)
        actions_layout = outer_layout
        actions_note = QtWidgets.QLabel(
            "Analysis Tools are for trace processing/display operations after choosing what to view or detect."
        )
        actions_note.setWordWrap(True)
        actions_layout.addWidget(actions_note)

        layout.addWidget(shared_group)

        window_quick_group = QtWidgets.QGroupBox("Window shortcuts (shared)")
        window_quick_layout = QtWidgets.QVBoxLayout(window_quick_group)

        quick_window_note = QtWidgets.QLabel(
            "These edit the same detection windows shown in the Windows tab."
        )
        quick_window_note.setWordWrap(True)
        window_quick_layout.addWidget(quick_window_note)

        quick_window_buttons = QtWidgets.QHBoxLayout()
        quick_window_buttons.setSpacing(4)
        add_window_button_detect = QtWidgets.QPushButton("Add")
        add_window_button_detect.clicked.connect(self.add_detection_window)
        quick_window_buttons.addWidget(add_window_button_detect)

        generate_windows_button_detect = QtWidgets.QPushButton("Gen")
        generate_windows_button_detect.clicked.connect(self.generate_stimulus_windows)
        quick_window_buttons.addWidget(generate_windows_button_detect)

        clear_window_button_detect = QtWidgets.QPushButton("Clear")
        clear_window_button_detect.clicked.connect(self.clear_detection_windows)
        quick_window_buttons.addWidget(clear_window_button_detect)

        add_window_button_detect.setToolTip("Add one manual detection window.")
        generate_windows_button_detect.setToolTip("Generate repeated windows from the Windows tab settings.")
        clear_window_button_detect.setToolTip("Clear all detection windows.")
        for button in (add_window_button_detect, generate_windows_button_detect, clear_window_button_detect):
            button.setMinimumWidth(0)
            button.setMinimumHeight(28)
            button.setToolTip(button.toolTip())

        window_quick_layout.addLayout(quick_window_buttons)

        threshold_group = QtWidgets.QGroupBox("Threshold detection")
        threshold_layout = QtWidgets.QVBoxLayout(threshold_group)

        self.threshold_readout = QtWidgets.QLabel("Threshold: 0")
        self.threshold_readout.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.threshold_readout.setVisible(False)

        self.threshold_auto_button = QtWidgets.QPushButton("Center Threshold on Trace")
        self.threshold_auto_button.clicked.connect(self.auto_threshold)
        threshold_layout.addWidget(self.threshold_auto_button)

        self.advanced_detection_box = CollapsibleBox("Advanced detection settings")
        advanced_layout = self.advanced_detection_box.content_layout()

        self.detect_direction_combo = QtWidgets.QComboBox()
        self.detect_direction_combo.addItems(
            ["Auto from threshold", "Below threshold / downward", "Above threshold / upward"]
        )
        self.detect_direction_combo.setCurrentText("Auto from threshold")
        advanced_layout.addWidget(QtWidgets.QLabel("Detect direction:"))
        advanced_layout.addWidget(self.detect_direction_combo)

        threshold_advanced_label = QtWidgets.QLabel("Manual threshold:")
        threshold_advanced_label.setWordWrap(True)
        advanced_layout.addWidget(threshold_advanced_label)

        self.threshold_edit = QtWidgets.QLineEdit("0")
        self.threshold_edit.returnPressed.connect(self._threshold_edit_finished)
        self.threshold_edit.setToolTip("Enter an exact threshold value, then press Return.")
        advanced_layout.addWidget(self.threshold_edit)

        self.threshold_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(1000)
        self.threshold_slider.valueChanged.connect(self._threshold_slider_changed)
        self.threshold_slider.setToolTip("Drag to adjust threshold within the current trace range.")
        advanced_layout.addWidget(self.threshold_slider)

        self.min_spacing_spin = NoWheelDoubleSpinBox()
        self.min_spacing_spin.setRange(0.0, 10000.0)
        self.min_spacing_spin.setDecimals(3)
        self.min_spacing_spin.setSingleStep(0.1)
        self.min_spacing_spin.setValue(2.0)
        self.min_spacing_spin.valueChanged.connect(self.update_spacing_readout)
        min_spacing_label = QtWidgets.QLabel("Min spacing / width (ms):")
        min_spacing_label.setWordWrap(True)
        advanced_layout.addWidget(min_spacing_label)
        advanced_layout.addWidget(self.min_spacing_spin)

        self.smoothing_spin = NoWheelSpinBox()
        self.smoothing_spin.setRange(1, 1000)
        self.smoothing_spin.setValue(1)
        smoothing_label = QtWidgets.QLabel("Smoothing box points:")
        smoothing_label.setWordWrap(True)
        advanced_layout.addWidget(smoothing_label)
        advanced_layout.addWidget(self.smoothing_spin)

        self.min_delta_spin = NoWheelDoubleSpinBox()
        self.min_delta_spin.setRange(0.0, 1e12)
        self.min_delta_spin.setDecimals(9)
        self.min_delta_spin.setSingleStep(0.1)
        self.min_delta_spin.setValue(0.0)
        self.min_delta_spin.setToolTip(
            "Leave at 0 for automatic noise rejection. Use a positive value only if tiny near-threshold wiggles are being counted as spikes."
        )
        min_delta_label = QtWidgets.QLabel("Ignore tiny threshold wiggles (0 = auto):")
        min_delta_label.setWordWrap(True)
        min_delta_label.setToolTip(self.min_delta_spin.toolTip())
        advanced_layout.addWidget(min_delta_label)
        advanced_layout.addWidget(self.min_delta_spin)

        self.spacing_readout = QtWidgets.QLabel("")
        advanced_layout.addWidget(self.spacing_readout)

        threshold_layout.addWidget(self.advanced_detection_box)

        layout.addWidget(threshold_group)
        layout.addWidget(window_quick_group)
        layout.addStretch()

        window_group = QtWidgets.QGroupBox("Stimulus detection windows / cursor pairs")
        window_layout = QtWidgets.QVBoxLayout(window_group)

        intro = QtWidgets.QLabel(
            "Generate windows for any stimulus frequency. Add One Manual Window creates a single cursor-pair region; "
            "Generate Stimulus Windows creates repeated regions from onset, frequency, width, and count."
        )
        window_layout.addWidget(intro)

        find_button_windows = QtWidgets.QPushButton("Find Events in Windows")
        find_button_windows.clicked.connect(self.find_spikes)
        find_button_windows.setToolTip("Run spike/event detection using the current threshold and active windows.")
        window_layout.addWidget(find_button_windows)

        stim_grid = QtWidgets.QGridLayout()
        stim_grid.setColumnStretch(1, 1)

        stim_grid.addWidget(QtWidgets.QLabel("Onset ms:"), 0, 0)
        self.stim_onset_ms_spin = NoWheelDoubleSpinBox()
        self.stim_onset_ms_spin.setRange(0.0, 1e9)
        self.stim_onset_ms_spin.setDecimals(0)
        self.stim_onset_ms_spin.setValue(100.0)
        stim_grid.addWidget(self.stim_onset_ms_spin, 0, 1)

        stim_grid.addWidget(QtWidgets.QLabel("Hz:"), 1, 0)
        self.stim_frequency_hz_spin = NoWheelDoubleSpinBox()
        self.stim_frequency_hz_spin.setRange(0.001, 100000.0)
        self.stim_frequency_hz_spin.setDecimals(3)
        self.stim_frequency_hz_spin.setValue(20.0)
        self.stim_frequency_hz_spin.valueChanged.connect(self.frequency_value_changed)
        stim_grid.addWidget(self.stim_frequency_hz_spin, 1, 1)

        self.frequency_period_label = QtWidgets.QLabel("Period: 50 ms; half: 25 ms")
        self.frequency_period_label.setToolTip("Computed from frequency: period = 1000 / frequency Hz.")
        stim_grid.addWidget(self.frequency_period_label, 2, 0, 1, 2)

        stim_grid.addWidget(QtWidgets.QLabel("Width ms:"), 3, 0)
        self.stim_window_width_ms_spin = NoWheelDoubleSpinBox()
        self.stim_window_width_ms_spin.setRange(1.0, 1e9)
        self.stim_window_width_ms_spin.setDecimals(0)
        self.stim_window_width_ms_spin.setValue(25.0)
        stim_grid.addWidget(self.stim_window_width_ms_spin, 3, 1)

        stim_grid.addWidget(QtWidgets.QLabel("Count:"), 4, 0)
        self.stim_window_count_spin = NoWheelSpinBox()
        self.stim_window_count_spin.setRange(1, 10000)
        self.stim_window_count_spin.setValue(1)
        stim_grid.addWidget(self.stim_window_count_spin, 4, 1)

        self.paired_windows_checkbox = QtWidgets.QCheckBox("Generate paired second window")
        self.paired_windows_checkbox.setChecked(False)
        stim_grid.addWidget(self.paired_windows_checkbox, 5, 0, 1, 2)

        stim_grid.addWidget(QtWidgets.QLabel("2nd gap ms:"), 6, 0)
        self.pair_offset_ms_spin = NoWheelDoubleSpinBox()
        self.pair_offset_ms_spin.setRange(-1e9, 1e9)
        self.pair_offset_ms_spin.setDecimals(0)
        self.pair_offset_ms_spin.setValue(100.0)
        self.pair_offset_ms_spin.setToolTip(
            "Start of second window relative to start of first window."
        )
        stim_grid.addWidget(self.pair_offset_ms_spin, 6, 1)

        stim_grid.addWidget(QtWidgets.QLabel("2nd width ms:"), 7, 0)
        self.pair_width_ms_spin = NoWheelDoubleSpinBox()
        self.pair_width_ms_spin.setRange(1.0, 1e9)
        self.pair_width_ms_spin.setDecimals(0)
        self.pair_width_ms_spin.setValue(25.0)
        self.pair_width_ms_spin.setEnabled(True)
        self.pair_width_ms_spin.setToolTip("Starts matched to the first-window width, but can be edited manually.")
        stim_grid.addWidget(self.pair_width_ms_spin, 7, 1)

        self.paired_windows_checkbox.toggled.connect(self.sync_pair_width_to_first_if_needed)

        window_layout.addLayout(stim_grid)

        win_buttons = QtWidgets.QVBoxLayout()
        add_window_button = QtWidgets.QPushButton("Add One Manual Window")
        add_window_button.clicked.connect(self.add_detection_window)
        win_buttons.addWidget(add_window_button)

        clear_window_button = QtWidgets.QPushButton("Clear Windows")
        clear_window_button.clicked.connect(self.clear_detection_windows)
        win_buttons.addWidget(clear_window_button)
        window_layout.addLayout(win_buttons)

        quick20_button = QtWidgets.QPushButton("20 Hz defaults")
        quick20_button.clicked.connect(self.set_20hz_window_defaults)
        window_layout.addWidget(quick20_button)

        generate_windows_button = QtWidgets.QPushButton("Gen")
        generate_windows_button.clicked.connect(self.generate_stimulus_windows)
        window_layout.addWidget(generate_windows_button)

        self.window_summary_windows_tab = QtWidgets.QLabel("No windows. Detection uses full trace.")
        window_layout.addWidget(self.window_summary_windows_tab)

        windows_layout_tab.addWidget(window_group)
        windows_layout_tab.addStretch()

        autoscale_action_button = QtWidgets.QPushButton("Autoscale Displayed Traces")
        autoscale_action_button.clicked.connect(self.autoscale_displayed_traces)
        actions_layout.addWidget(autoscale_action_button)

        baseline_actions_group = QtWidgets.QGroupBox("Baseline")
        baseline_actions_layout = QtWidgets.QVBoxLayout(baseline_actions_group)

        baseline_scope_note = QtWidgets.QLabel("Uses the top-panel Baseline options: Keep baseline and All selected.")
        baseline_scope_note.setWordWrap(True)
        baseline_actions_layout.addWidget(baseline_scope_note)

        baseline_button = QtWidgets.QPushButton("Baseline Subtract")
        baseline_button.clicked.connect(self.baseline_subtract_scope)
        baseline_actions_layout.addWidget(baseline_button)

        clear_baseline_button = QtWidgets.QPushButton("Clear Persistent Baseline")
        clear_baseline_button.clicked.connect(self.clear_persistent_baseline)
        baseline_actions_layout.addWidget(clear_baseline_button)

        actions_layout.addWidget(baseline_actions_group)

        avg_button = QtWidgets.QPushButton("Average Selected Series")
        avg_button.clicked.connect(self.show_average)
        actions_layout.addWidget(avg_button)

        fft_button = QtWidgets.QPushButton("FFT Current/Displayed Sweep")
        fft_button.clicked.connect(self.show_fft)
        actions_layout.addWidget(fft_button)

        concat_button = QtWidgets.QPushButton("Concatenate Selected Sweeps")
        concat_button.clicked.connect(self.show_concatenated)
        actions_layout.addWidget(concat_button)

        actions_layout.addStretch()


    def _build_field_potential_tab(self) -> None:
        layout = self._make_scrollable_tab(self.field_potential_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        settings_group = QtWidgets.QGroupBox("Field-potential settings")
        settings_layout = QtWidgets.QGridLayout(settings_group)

        self.fp_stim_onset_spin = NoWheelDoubleSpinBox()
        self.fp_stim_onset_spin.setRange(0.0, 10000.0)
        self.fp_stim_onset_spin.setDecimals(3)
        self.fp_stim_onset_spin.setSingleStep(0.001)
        self.fp_stim_onset_spin.setValue(0.050)

        self.fp_stim_length_spin = NoWheelDoubleSpinBox()
        self.fp_stim_length_spin.setRange(0.0, 10000.0)
        self.fp_stim_length_spin.setDecimals(3)
        self.fp_stim_length_spin.setSingleStep(0.001)
        self.fp_stim_length_spin.setValue(0.050)

        self.fp_search_offset_spin = NoWheelDoubleSpinBox()
        self.fp_search_offset_spin.setRange(0.0, 10000.0)
        self.fp_search_offset_spin.setDecimals(3)
        self.fp_search_offset_spin.setSingleStep(0.001)
        self.fp_search_offset_spin.setValue(0.001)

        self.fp_rms_window_spin = NoWheelDoubleSpinBox()
        self.fp_rms_window_spin.setRange(0.000001, 10000.0)
        self.fp_rms_window_spin.setDecimals(3)
        self.fp_rms_window_spin.setSingleStep(0.001)
        self.fp_rms_window_spin.setValue(0.050)

        self.fp_rms_sigma_spin = NoWheelDoubleSpinBox()
        self.fp_rms_sigma_spin.setRange(0.0, 1000.0)
        self.fp_rms_sigma_spin.setDecimals(2)
        self.fp_rms_sigma_spin.setSingleStep(0.05)
        self.fp_rms_sigma_spin.setValue(0.20)

        self.fp_baseline_checkbox = QtWidgets.QCheckBox("Baseline subtract final RMS-window mean")
        self.fp_baseline_checkbox.setChecked(True)

        for spin in (
            self.fp_stim_onset_spin,
            self.fp_stim_length_spin,
            self.fp_search_offset_spin,
            self.fp_rms_window_spin,
            self.fp_rms_sigma_spin,
        ):
            spin.setMaximumWidth(82)
            spin.setMinimumWidth(72)

        settings_layout.setHorizontalSpacing(6)
        settings_layout.setVerticalSpacing(4)
        settings_layout.setColumnStretch(0, 0)
        settings_layout.setColumnStretch(1, 0)
        settings_layout.setColumnStretch(2, 0)
        settings_layout.setColumnStretch(3, 0)

        fields = [
            ("Onset (s)", self.fp_stim_onset_spin),
            ("Length (s)", self.fp_stim_length_spin),
            ("Offset (s)", self.fp_search_offset_spin),
            ("RMS win (s)", self.fp_rms_window_spin),
            ("RMS tol", self.fp_rms_sigma_spin),
        ]
        for i, (label, widget) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            lbl = QtWidgets.QLabel(label)
            lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            settings_layout.addWidget(lbl, row, col)
            settings_layout.addWidget(widget, row, col + 1)
        settings_layout.addWidget(self.fp_baseline_checkbox, 3, 0, 1, 4)
        layout.addWidget(settings_group)

        actions_group = QtWidgets.QGroupBox("Run FP analysis")
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        row1 = QtWidgets.QHBoxLayout()
        analyze_current = QtWidgets.QPushButton("Analyze Current Sweep")
        analyze_current.clicked.connect(self.fp_analyze_current_sweep)
        row1.addWidget(analyze_current)
        analyze_selected = QtWidgets.QPushButton("Analyze Selected Sweeps")
        analyze_selected.clicked.connect(self.fp_analyze_selected_sweeps)
        row1.addWidget(analyze_selected)
        actions_layout.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        show_selected = QtWidgets.QPushButton("Show Selected FP Row")
        show_selected.clicked.connect(self.fp_show_selected_result)
        row2.addWidget(show_selected)
        export_fp = QtWidgets.QPushButton("Export FP CSV")
        export_fp.clicked.connect(self.fp_export_csv)
        row2.addWidget(export_fp)
        actions_layout.addLayout(row2)

        clear_fp = QtWidgets.QPushButton("Clear FP Results")
        clear_fp.clicked.connect(self.fp_clear_results)
        actions_layout.addWidget(clear_fp)

        note = QtWidgets.QLabel(
            "Port of BT_FieldPotentialBatch_v2_15 automatic analysis. "
            "Markers: onset, peak, trough, and RMS return. Select a row and click Show Selected FP Row to review annotations."
        )
        note.setWordWrap(True)
        actions_layout.addWidget(note)
        layout.addWidget(actions_group)

        fp_results_note = QtWidgets.QLabel(
            "FP results are shown in the larger results area below the graph. "
            "Use the Field Potential results tab there for reviewing rows and double-clicking a row."
        )
        fp_results_note.setWordWrap(True)
        layout.addWidget(fp_results_note)

        layout.addStretch()


    def _build_display_tab(self) -> None:
        layout = self._make_scrollable_tab(self.display_tab)

        display_wave = QtWidgets.QPushButton("Display Current Sweep")
        display_wave.clicked.connect(self.update_plot)
        layout.addWidget(display_wave)

        display_avg = QtWidgets.QPushButton("Display Average")
        display_avg.clicked.connect(self.show_average)
        layout.addWidget(display_avg)

        display_s2 = QtWidgets.QPushButton("Display Matching S2")
        display_s2.clicked.connect(self.show_matching_s2)
        display_s2.setToolTip("Display the simultaneously recorded S2 input signal matching the current routine/sweep.")
        layout.addWidget(display_s2)

        display_stim = QtWidgets.QPushButton("Display Stimulus Waveform")
        display_stim.clicked.connect(self.show_matching_stimulus)
        display_stim.setToolTip("Display an output/stimulus waveform preview from the PXP file, not the recorded S2 channel.")
        layout.addWidget(display_stim)

        choose_stim = QtWidgets.QPushButton("Choose Output Source")
        choose_stim.clicked.connect(self.choose_stimulus_source)
        choose_stim.setToolTip("Inspect stored output/stimulus candidates. AppControl preview-only sources are not authoritative.")
        layout.addWidget(choose_stim)

        overlay_stim = QtWidgets.QPushButton("Overlay Stimulus on Sweep")
        overlay_stim.clicked.connect(self.overlay_matching_stimulus)
        overlay_stim.setToolTip("Overlay the stimulus waveform on the currently selected sweep using a separate right Y axis.")
        layout.addWidget(overlay_stim)

        hist_button = QtWidgets.QPushButton("Display ISI Histogram")
        hist_button.clicked.connect(self.show_event_histogram)
        hist_button.setToolTip("Plot inter-spike intervals: spike_time(n+1) - spike_time(n).")
        layout.addWidget(hist_button)

        clear_button = QtWidgets.QPushButton("Clear Plot")
        clear_button.clicked.connect(self.clear_plot)
        layout.addWidget(clear_button)

        layout.addStretch()

    def _fmt_value(self, value, decimals: int = 2) -> str:
        """Format numeric GUI values compactly without hiding tiny values.

        Ordinary values use fixed decimal places. Very small/large values use
        scientific notation with the same number of mantissa decimals.
        """
        try:
            v = float(value)
        except Exception:
            return str(value)
        if not np.isfinite(v):
            return str(value)
        if v == 0:
            return "0"

        av = abs(v)
        if av < 0.01 or av >= 10000:
            return f"{v:.{decimals}e}"
        return f"{v:.{decimals}f}"

    def _fmt_time(self, value) -> str:
        """Format time values in seconds.

        Times are usually useful at millisecond-ish precision, so keep 4 decimals
        for ordinary second values and scientific notation for very small values.
        """
        try:
            v = float(value)
        except Exception:
            return str(value)
        if not np.isfinite(v):
            return str(value)
        if v == 0:
            return "0"
        if abs(v) < 1e-4:
            return f"{v:.2e}"
        return f"{v:.4g}"


    @QtCore.Slot()
    def previous_sweep(self) -> None:
        self.sweep_spin.setValue(max(self.sweep_spin.minimum(), self.sweep_spin.value() - 1))

    @QtCore.Slot(str)
    def _signal_filter_changed(self, _text: str = "") -> None:
        """Refresh series and plot when S1/S2/All selection changes."""
        self.on_signal_changed()

    @QtCore.Slot(int)
    def _series_selection_changed(self, _index: int = 0) -> None:
        """Compatibility slot for the compact Series dropdown."""
        if hasattr(self, "series_combo"):
            self.series_combo.setToolTip(self.series_combo.currentText())
        if hasattr(self, "update_series_controls"):
            self.update_series_controls()
        elif hasattr(self, "series_changed"):
            self.series_changed()
        elif hasattr(self, "on_series_changed"):
            self.on_series_changed()
        elif hasattr(self, "_series_changed"):
            self._series_changed()
        else:
            # Generic fallback: update sweep limits and redraw current plot.
            series = self._current_series() if hasattr(self, "_current_series") else None
            if series is not None and hasattr(self, "sweep_spin"):
                self.sweep_spin.blockSignals(True)
                self.sweep_spin.setRange(1, max(1, int(series.sweep_count)))
                self.sweep_spin.setValue(min(self.sweep_spin.value(), max(1, int(series.sweep_count))))
                self.sweep_spin.blockSignals(False)
            if hasattr(self, "update_plot"):
                self.update_plot()
                self._request_full_autoscale()

    @QtCore.Slot()
    def load_file(self) -> None:
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load electrophysiology file",
            "",
            "Data files (*.pxp *.ibw *.abf *.csv);;All files (*)",
        )
        if not path_str:
            return
        try:
            recording = load_any(Path(path_str))
        except LoaderError as exc:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(exc))
            return

        self.state.recording = recording
        self.state.data_type = recording.source_format.upper()
        self.state.sweep_start = 1
        self.state.sweep_end = max(1, recording.sweep_count)
        self.state.sweep_current = 1

        self._populate_signal_combo(default_signal="S1")
        self._populate_series_combo()

        report = recording.metadata.get("parse_report", {})
        skipped = report.get("records_skipped", 0)
        skip_msg = f"\nSkipped {skipped} malformed PXP record(s)." if skipped else ""
        self.info_label.setText(
            f"{recording.path.name if recording.path else 'Recording'}\n"
            f"{len(recording.series)} series, {recording.sweep_count} sweeps loaded from {recording.source_format}"
            f"{skip_msg}"
        )
        self.tabs.setCurrentWidget(self.detect_events_tab)
        self.update_spacing_readout()
        self.update_plot()
        try:
            QtCore.QTimer.singleShot(0, self.auto_threshold)
        except Exception:
            self.auto_threshold()

    def _populate_signal_combo(self, default_signal: str = "S1") -> None:
        recording = self.state.recording
        self.signal_combo.blockSignals(True)
        self.signal_combo.clear()
        self.signal_combo.addItem("All", None)

        signals: list[int] = []
        if recording is not None:
            for series in recording.series:
                sig = series.metadata.get("signal_number")
                if sig is None:
                    m = re.search(r"(?:^|_)S(\d+)(?:_|$)", series.name)
                    sig = int(m.group(1)) if m else None
                try:
                    sig_int = int(sig) if sig is not None else None
                except Exception:
                    sig_int = None
                if sig_int is not None and sig_int not in signals:
                    signals.append(sig_int)

        for sig in sorted(signals):
            self.signal_combo.addItem(f"S{sig}", sig)

        default_index = self.signal_combo.findText(default_signal)
        self.signal_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        self.signal_combo.blockSignals(False)

    def _populate_series_combo(self) -> None:
        recording = self.state.recording
        self.series_combo.blockSignals(True)
        self.series_combo.clear()
        self._available_series = []

        if recording is None:
            self.series_combo.addItem("No recording", None)
        elif recording.series:
            selected_signal = self.signal_combo.currentData()
            for series in recording.series:
                if selected_signal is not None:
                    sig = series.metadata.get("signal_number")
                    if sig is None:
                        m = re.search(r"(?:^|_)S(\d+)(?:_|$)", series.name)
                        sig = int(m.group(1)) if m else None
                    try:
                        sig = int(sig) if sig is not None else None
                    except Exception:
                        sig = None
                    if sig != selected_signal:
                        continue
                self._available_series.append(series)
                label = f"{series.name} ({series.sweep_count} sweeps, {series.point_count} points)"
                self.series_combo.addItem(label, series.name)

            if not self._available_series:
                self.series_combo.addItem("No series for selected signal", None)
        else:
            self.series_combo.addItem("All sweeps", "")

        self.series_combo.blockSignals(False)
        self.sweep_spin.blockSignals(True)
        self.sweep_spin.setMaximum(max(1, self._current_sweep_count()))
        self.sweep_spin.setValue(1)
        self.sweep_spin.blockSignals(False)

    def _disable_plot_autorange(self) -> None:
        """Ensure pyqtgraph is not left recomputing bounds during interaction."""
        try:
            vb = self.plot.getViewBox()
            vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=False)
        except Exception:
            try:
                self.plot.disableAutoRange()
            except Exception:
                pass

    def _sample_for_range(self, arr, max_points: int = 5000):
        """Small display-range sample; avoids expensive full scans on many traces."""
        a = np.asarray(arr, dtype=float)
        if a.size > max_points:
            step = max(1, int(np.ceil(a.size / max_points)))
            a = a[::step]
        return a[np.isfinite(a)]

    def _explicit_full_range_from_traces(self, traces: list[DisplayTrace], preserve_x=None) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        """Compute explicit X/Y ranges from displayed traces without enabling autoRange."""
        if not traces:
            return None, None

        # X: timebases are normally monotonic; endpoints are enough and much faster.
        xmin = xmax = None
        if preserve_x is not None:
            try:
                (px0, px1), _ = preserve_x
                if np.isfinite(px0) and np.isfinite(px1) and px0 < px1:
                    xmin, xmax = float(px0), float(px1)
            except Exception:
                xmin = xmax = None

        if xmin is None or xmax is None:
            xmins = []
            xmaxs = []
            for tr in traces:
                x = np.asarray(tr.x, dtype=float) if tr.x is not None else np.array([])
                if x.size:
                    # Use finite endpoints if possible; fall back to sampled scan.
                    candidates = []
                    for val in (x[0], x[-1]):
                        if np.isfinite(val):
                            candidates.append(float(val))
                    if len(candidates) >= 2:
                        xmins.append(min(candidates))
                        xmaxs.append(max(candidates))
                    else:
                        xs = self._sample_for_range(x)
                        if xs.size:
                            xmins.append(float(np.nanmin(xs)))
                            xmaxs.append(float(np.nanmax(xs)))
            if xmins and xmaxs:
                xmin = min(xmins)
                xmax = max(xmaxs)

        # Y: ignore stimulus when signal traces are present, as stimulus uses right axis.
        y_source = [tr for tr in traces if tr.source != "stimulus"] or traces
        ymins = []
        ymaxs = []
        units = ""
        for tr in y_source:
            ys = self._sample_for_range(tr.y)
            if ys.size:
                ymins.append(float(np.nanmin(ys)))
                ymaxs.append(float(np.nanmax(ys)))
                if not units:
                    units = str(getattr(tr, "units", "") or "").strip().lower()

        x_range = None
        if xmin is not None and xmax is not None and np.isfinite(xmin) and np.isfinite(xmax):
            if xmin == xmax:
                xmin -= 0.5
                xmax += 0.5
            if preserve_x is not None:
                # Preserve the current X window exactly. Re-padding an already
                # padded range caused the X axis to drift with repeated Baseline
                # presses.
                x_range = (xmin, xmax)
            else:
                xpad = 0.01 * (xmax - xmin)
                x_range = (xmin - xpad, xmax + xpad)

        y_range = None
        if ymins and ymaxs:
            ymin = min(ymins)
            ymax = max(ymaxs)
            center = 0.5 * (ymin + ymax)
            span = ymax - ymin
            if not np.isfinite(span) or span <= 0:
                span = abs(center) if center else 1.0

            # Avoid over-zooming very quiet voltage traces, but do not leave
            # pyqtgraph autorange enabled.
            min_span = 0.0
            max_abs = max(abs(ymin), abs(ymax), abs(center))
            if units in {"v", "volt", "volts"} and max_abs < 0.2:
                min_span = 1e-3
            elif units in {"mv", "millivolt", "millivolts"}:
                min_span = 1.0

            display_span = max(span, min_span)
            ypad = max(0.08 * display_span, 0.5 * (display_span - span))
            y_range = (ymin - ypad, ymax + ypad)

        return x_range, y_range

    def _range_from_xy_matrix(self, x, y_matrix, preserve_x=None, units: str = "") -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        """Fast range calculation for matrix-shaped plotted data.

        This is used for baseline overlays so Autoscale can reuse a cached range
        instead of walking every displayed DisplayTrace.
        """
        try:
            x_arr = np.asarray(x, dtype=float)
            y_arr = np.asarray(y_matrix, dtype=float)
        except Exception:
            return None, None
        if y_arr.ndim == 1:
            y_arr = y_arr[:, None]

        xmin = xmax = None
        if preserve_x is not None:
            try:
                (px0, px1), _ = preserve_x
                if np.isfinite(px0) and np.isfinite(px1) and px0 < px1:
                    xmin, xmax = float(px0), float(px1)
            except Exception:
                xmin = xmax = None
        if xmin is None or xmax is None:
            if x_arr.size:
                finite_x = x_arr[np.isfinite(x_arr)]
                if finite_x.size:
                    xmin = float(finite_x[0])
                    xmax = float(finite_x[-1])
                    if xmin > xmax:
                        xmin, xmax = xmax, xmin

        y_sample = y_arr
        if x_arr.size == y_arr.shape[0] and xmin is not None and xmax is not None:
            mask = np.isfinite(x_arr) & (x_arr >= xmin) & (x_arr <= xmax)
            if np.any(mask):
                y_sample = y_arr[mask, :]
        # Keep this bounded even for very long traces.
        if y_sample.shape[0] > 5000:
            step = max(1, int(np.ceil(y_sample.shape[0] / 5000)))
            y_sample = y_sample[::step, :]
        finite_y = y_sample[np.isfinite(y_sample)]
        if finite_y.size:
            ymin = float(np.nanmin(finite_y))
            ymax = float(np.nanmax(finite_y))
        else:
            ymin = ymax = None

        x_range = None
        if xmin is not None and xmax is not None and np.isfinite(xmin) and np.isfinite(xmax):
            if xmin == xmax:
                xmin -= 0.5
                xmax += 0.5
            xpad = 0.01 * (xmax - xmin)
            x_range = (xmin - xpad, xmax + xpad)

        y_range = None
        if ymin is not None and ymax is not None:
            span = ymax - ymin
            center = 0.5 * (ymin + ymax)
            if not np.isfinite(span) or span <= 0:
                span = abs(center) if center else 1.0
            units = str(units or "").strip().lower()
            min_span = 0.0
            max_abs = max(abs(ymin), abs(ymax), abs(center))
            if units in {"v", "volt", "volts"} and max_abs < 0.2:
                min_span = 1e-3
            elif units in {"mv", "millivolt", "millivolts"}:
                min_span = 1.0
            display_span = max(span, min_span)
            ypad = max(0.08 * display_span, 0.5 * (display_span - span))
            y_range = (ymin - ypad, ymax + ypad)

        return x_range, y_range

    def _apply_cached_or_explicit_range(self, traces: list[DisplayTrace] | None = None, preserve_x=None) -> None:
        """Apply cached display range when available; otherwise compute one."""
        cached = getattr(self, "_cached_display_range", None)
        self._disable_plot_autorange()
        if cached:
            x_range, y_range = cached
            if preserve_x is not None:
                try:
                    (px0, px1), _ = preserve_x
                    if np.isfinite(px0) and np.isfinite(px1) and px0 < px1:
                        x_range = (float(px0), float(px1))
                except Exception:
                    pass
            if x_range is not None:
                try:
                    self.plot.setXRange(x_range[0], x_range[1], padding=0)
                except Exception:
                    pass
            if y_range is not None:
                try:
                    self.plot.setYRange(y_range[0], y_range[1], padding=0)
                except Exception:
                    pass
            return
        self._apply_explicit_range(list(traces or []), preserve_x=preserve_x)

    def _apply_range_from_xy(self, x, y, units: str = "") -> None:
        """Apply a fast explicit range from already display-sized x/y arrays."""
        x_range, y_range = self._range_from_xy_matrix(x, np.asarray(y, dtype=float), preserve_x=None, units=units)
        self._cached_display_range = (x_range, y_range)
        self._disable_plot_autorange()
        if x_range is not None:
            try:
                self.plot.setXRange(x_range[0], x_range[1], padding=0)
            except Exception:
                pass
        if y_range is not None:
            try:
                self.plot.setYRange(y_range[0], y_range[1], padding=0)
            except Exception:
                pass

    def _apply_explicit_range(self, traces: list[DisplayTrace], preserve_x=None) -> None:
        """Apply explicit ranges and then keep pyqtgraph autoRange disabled."""
        x_range, y_range = self._explicit_full_range_from_traces(traces, preserve_x=preserve_x)
        self._disable_plot_autorange()
        if x_range is not None:
            try:
                self.plot.setXRange(x_range[0], x_range[1], padding=0)
            except Exception:
                pass
        if y_range is not None:
            try:
                self.plot.setYRange(y_range[0], y_range[1], padding=0)
            except Exception:
                pass

    def _autoscale_full_plot(self) -> None:
        """Autoscale displayed traces explicitly without leaving autoRange enabled."""
        traces = list(getattr(self, "_range_traces", []) or getattr(self, "_displayed_traces", []) or [])
        if not traces:
            # Important: with no data, pyqtgraph autoRange can progressively
            # expand/warp the empty Y range on repeated presses. Do nothing.
            self._disable_plot_autorange()
            return
        self._apply_explicit_range(traces)


    def _request_full_autoscale(self) -> None:
        """Autoscale now and once after Qt finishes laying out new curves."""
        self._autoscale_full_plot()
        try:
            QtCore.QTimer.singleShot(0, self._autoscale_full_plot)
        except Exception:
            pass


    @QtCore.Slot()
    def on_signal_changed(self) -> None:
        self._populate_series_combo()
        self.update_plot()
        try:
            QtCore.QTimer.singleShot(0, self.auto_threshold)
        except Exception:
            self.auto_threshold()

    def _current_series(self):
        if not self._available_series:
            return None
        idx = max(0, self.series_combo.currentIndex())
        if idx >= len(self._available_series):
            return None
        return self._available_series[idx]

    def _current_sweep_count(self) -> int:
        series = self._current_series()
        if series is not None:
            return series.sweep_count
        recording = self.state.recording
        return recording.sweep_count if recording is not None else 1

    def _current_sweep(self):
        recording = self.state.recording
        if recording is None:
            return None
        series = self._current_series()
        if series is not None:
            idx = current_sweep_index(self.sweep_spin.value(), series.sweep_count)
            return series.sweep(idx)
        if recording.sweeps:
            idx = current_sweep_index(self.sweep_spin.value(), recording.sweep_count)
            return recording.sweeps[idx]
        return None

    def _trace_from_sweep(self, sweep, series_name: str = "", sweep_index: int = 0, source: str = "raw") -> DisplayTrace:
        x = np.asarray(sweep.timebase(), dtype=float)
        y = np.asarray(sweep.y, dtype=float)
        return DisplayTrace(
            x=x,
            y=y,
            series_name=series_name,
            sweep_index=sweep_index,
            display_name=sweep.name,
            sampling_interval=sweep.sampling_interval,
            units=sweep.units,
            source=source,
        )

    def _trace_key(self, series_name: str, sweep_index: int) -> tuple[str, int]:
        return (series_name or "", int(sweep_index))

    def _maybe_apply_persistent_baseline(self, trace: DisplayTrace) -> DisplayTrace:
        if not getattr(self, "baseline_persist_checkbox", None) or not self.baseline_persist_checkbox.isChecked():
            return trace
        if not self._baseline_enabled_by_trace_key.get(self._trace_key(trace.series_name, trace.sweep_index), False):
            return trace
        return DisplayTrace(
            x=trace.x,
            y=baseline_subtract(trace.y),
            series_name=trace.series_name,
            sweep_index=trace.sweep_index,
            display_name=trace.display_name + " baseline-subtracted",
            sampling_interval=trace.sampling_interval,
            units=trace.units,
            source="baseline_subtracted",
        )

    def _clear_stimulus_right_axis(self) -> None:
        """Remove prior right-axis stimulus overlay and disconnect its callbacks.

        Earlier versions removed the right-axis ViewBox but left its resize
        callback connected to the main ViewBox. Repeated stimulus overlays could
        accumulate stale callbacks and old ViewBoxes, causing progressive lag
        during zoom/pan/threshold dragging.
        """
        try:
            slot = getattr(self, "_stimulus_right_axis_resize_slot", None)
            if slot is not None:
                self.plot.getViewBox().sigResized.disconnect(slot)
        except Exception:
            pass
        self._stimulus_right_axis_resize_slot = None

        if getattr(self, "_stimulus_right_axis_curve", None) is not None:
            try:
                if getattr(self, "_stimulus_right_axis_view", None) is not None:
                    self._stimulus_right_axis_view.removeItem(self._stimulus_right_axis_curve)
            except Exception:
                pass
        self._stimulus_right_axis_curve = None

        try:
            right_axis = self.plot.getAxis("right")
            try:
                right_axis.unlinkFromView()
            except Exception:
                try:
                    right_axis.linkToView(None)
                except Exception:
                    pass
        except Exception:
            pass

        if getattr(self, "_stimulus_right_axis_view", None) is not None:
            try:
                self._stimulus_right_axis_view.setXLink(None)
            except Exception:
                pass
            try:
                self.plot.scene().removeItem(self._stimulus_right_axis_view)
            except Exception:
                pass
        self._stimulus_right_axis_view = None

        try:
            self.plot.showAxis("right", False)
        except Exception:
            pass


    def _plot_stimulus_on_right_axis(self, stim_trace: DisplayTrace) -> None:
        """Overlay stimulus on an independent right Y axis linked to the same X axis."""
        # Be defensive: callers usually clear first, but avoid leaked views if a
        # direct path calls this while a right-axis overlay already exists.
        self._clear_stimulus_right_axis()

        self.plot.showAxis("right", True)
        right_axis = self.plot.getAxis("right")
        right_axis.setLabel(stim_trace.units or "Stimulus")

        stim_view = pg.ViewBox()
        self._stimulus_right_axis_view = stim_view
        self.plot.scene().addItem(stim_view)
        right_axis.linkToView(stim_view)
        stim_view.setXLink(self.plot)

        def update_views():
            try:
                stim_view.setGeometry(self.plot.getViewBox().sceneBoundingRect())
                stim_view.linkedViewChanged(self.plot.getViewBox(), stim_view.XAxis)
            except Exception:
                pass

        self._stimulus_right_axis_resize_slot = update_views
        update_views()
        try:
            self.plot.getViewBox().sigResized.connect(update_views)
        except Exception:
            pass

        curve = pg.PlotDataItem(stim_trace.x, stim_trace.y, pen=pg.mkPen((255, 140, 0), width=2))
        stim_view.addItem(curve)
        self._stimulus_right_axis_curve = curve

        try:
            y = np.asarray(stim_trace.y, dtype=float)
            y = y[np.isfinite(y)]
            if y.size:
                ymin, ymax = float(np.nanmin(y)), float(np.nanmax(y))
                if ymin == ymax:
                    ymin -= 0.5
                    ymax += 0.5
                pad = 0.08 * (ymax - ymin)
                stim_view.setYRange(ymin - pad, ymax + pad, padding=0)
        except Exception:
            pass


    def _display_decimated_xy(self, x, y, max_points: int = 12000):
        """Return a display-only decimated x/y copy for very long traces."""
        try:
            n = len(y)
        except Exception:
            return x, y
        if max_points <= 0 or n <= max_points:
            return x, y
        step = max(1, int(np.ceil(n / max_points)))
        return x[::step], y[::step]


    def _plot_display_trace(self, tr: DisplayTrace, pen=None):
        """Plot a trace directly using pyqtgraph's normal path."""
        if pen is not None:
            return self.plot.plot(tr.x, tr.y, pen=pen)
        return self.plot.plot(tr.x, tr.y)


    def _plot_overlay_traces_combined(self, traces: list[DisplayTrace], max_sweeps: int = 100, pen=None) -> None:
        """Legacy helper retained for compatibility; ordinary overlay now uses separate curves."""
        if not traces:
            return
        if pen is None:
            pen = pg.mkPen((180, 180, 180), width=1.25)
        for tr in traces[:max_sweeps]:
            self._plot_display_trace(tr, pen=pen)


    def _set_displayed_traces(self, traces: list[DisplayTrace], title: str = "", left_label: str | None = None) -> None:
        self._displayed_traces = traces
        self._range_traces = traces
        self._cached_display_range = None
        self._detection_marker_items = []
        self._clear_stimulus_right_axis()
        self._disable_plot_autorange()
        self.plot.clear()

        stimulus_traces = [tr for tr in traces if tr.source == "stimulus"]
        signal_traces = [tr for tr in traces if tr.source != "stimulus"]
        use_right_stim_axis = bool(stimulus_traces and signal_traces)

        for tr in signal_traces:
            if tr.source == "s2":
                self.plot.plot(tr.x, tr.y, pen=pg.mkPen((80, 160, 255), width=1.5))
            else:
                self.plot.plot(tr.x, tr.y, pen=pg.mkPen((220, 220, 220), width=1.25))

        if use_right_stim_axis:
            self._plot_stimulus_on_right_axis(stimulus_traces[0])
        else:
            for tr in stimulus_traces:
                self.plot.plot(tr.x, tr.y, pen=pg.mkPen((255, 140, 0), width=2))
            try:
                self.plot.showAxis("right", False)
            except Exception:
                pass

        if title:
            self.plot.setTitle(title)
        if traces:
            self.plot.setLabel("bottom", "Time", units="s")
            left_trace = signal_traces[0] if signal_traces else traces[0]
            self.plot.setLabel("left", left_label or left_trace.units or "Signal")

        self._readd_detection_windows_to_plot()
        self._ensure_threshold_line()
        if traces:
            self._update_threshold_slider_from_trace((signal_traces[0] if signal_traces else traces[0]).y)
            self.update_spacing_readout()

    @QtCore.Slot()
    def on_series_changed(self) -> None:
        self.sweep_spin.blockSignals(True)
        self.sweep_spin.setMaximum(max(1, self._current_sweep_count()))
        self.sweep_spin.setValue(1)
        self.sweep_spin.blockSignals(False)
        self.update_spacing_readout()
        self.update_plot()
        try:
            QtCore.QTimer.singleShot(0, self.auto_threshold)
        except Exception:
            self.auto_threshold()

    def _native_autorange_once(self) -> None:
        """Use pyqtgraph's native range calculation once, then disable live autoRange."""
        try:
            vb = self.plot.getViewBox()
            vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
            self.plot.autoRange(padding=0.02)
            vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=False)
        except Exception:
            try:
                self.plot.autoRange()
                self._disable_plot_autorange()
            except Exception:
                pass

    @QtCore.Slot()
    def update_plot(self) -> None:
        sweep = self._current_sweep()
        series = self._current_series()
        if sweep is None:
            return

        self._display_mode = "single"
        idx = self.sweep_spin.value() - 1
        tr = self._trace_from_sweep(sweep, series.name if series is not None else "", idx, source="raw")
        tr = self._maybe_apply_persistent_baseline(tr)

        # Keep current-sweep display as close as possible to the fast overlay
        # path: direct plot, no explicit range scans, no threshold-slider range
        # scan, no display helper. The previous _set_displayed_traces +
        # _apply_explicit_range path made single traces choppy, while overlay
        # remained responsive.
        self._displayed_traces = [tr]
        self._range_traces = [tr]
        self._cached_display_range = None
        self._detection_marker_items = []

        self._clear_stimulus_right_axis()
        self._disable_plot_autorange()
        self.plot.clear()
        self.plot.plot(tr.x, tr.y)

        self.plot.setTitle(tr.display_name)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", tr.units or "Signal")

        self._readd_detection_windows_to_plot()
        self._ensure_threshold_line()
        self.update_spacing_readout()

        # For a single trace, native pyqtgraph autorange is fast and avoids the
        # interaction lag caused by our explicit sampled range path.
        self._native_autorange_once()


    def _ensure_threshold_line(self) -> None:
        if self.threshold_line not in self.plot.items():
            self.plot.addItem(self.threshold_line)
        self.threshold_line.setVisible(True)
        try:
            self.threshold_line.setPen(self._threshold_idle_pen)
        except Exception:
            pass
        self.threshold_line.blockSignals(True)
        self.threshold_line.setPos(self.threshold_value())
        self.threshold_line.blockSignals(False)

    def threshold_value(self) -> float:
        try:
            return float(self.threshold_edit.text())
        except ValueError:
            return 0.0

    def _format_threshold_text(self, value: float) -> str:
        """Compact threshold formatting for edit/readout display."""
        try:
            value = float(value)
        except Exception:
            return str(value)
        if not np.isfinite(value):
            return str(value)
        av = abs(value)
        if av != 0 and (av < 0.001 or av >= 10000):
            return f"{value:.2e}"
        return f"{value:.6g}"

    def set_threshold_value(self, value: float, update_line: bool = True) -> None:
        value = float(value)
        txt = self._format_threshold_text(value)
        self.threshold_edit.blockSignals(True)
        self.threshold_edit.setText(txt)
        self.threshold_edit.blockSignals(False)
        self.threshold_readout.setText(f"Threshold: {txt}")
        if hasattr(self, "quick_threshold_readout"):
            self.quick_threshold_readout.setText(f"Threshold: {txt}")
        if update_line:
            try:
                self.threshold_line.setPen(self._threshold_idle_pen)
            except Exception:
                pass
            self.threshold_line.blockSignals(True)
            self.threshold_line.setPos(value)
            self.threshold_line.blockSignals(False)
        self._set_slider_from_threshold(value)

    @QtCore.Slot()
    def prev_sweep(self) -> None:
        self.sweep_spin.setValue(max(1, self.sweep_spin.value() - 1))

    @QtCore.Slot()
    def next_sweep(self) -> None:
        self.sweep_spin.setValue(min(self.sweep_spin.maximum(), self.sweep_spin.value() + 1))

    @QtCore.Slot()
    def _threshold_edit_finished(self) -> None:
        try:
            value = float(self.threshold_edit.text())
        except ValueError:
            self.set_threshold_value(self.threshold_value())
            return
        self.set_threshold_value(value)

    def _threshold_line_moved(self, *args) -> None:
        try:
            self.threshold_line.setPen(self._threshold_active_pen)
        except Exception:
            pass
        self.set_threshold_value(float(self.threshold_line.value()), update_line=False)

    def _threshold_line_released(self, *args) -> None:
        self.set_threshold_value(float(self.threshold_line.value()), update_line=False)
        try:
            self.threshold_line.setPen(self._threshold_idle_pen)
        except Exception:
            pass


    @QtCore.Slot(int)
    def _threshold_slider_changed(self, value: int) -> None:
        trace = self._reference_trace_for_controls()
        if trace is None:
            return
        ymin, ymax = self._threshold_range(trace.y)
        threshold = ymin + (ymax - ymin) * value / 1000.0
        self.set_threshold_value(threshold)

    def _reference_trace_for_controls(self) -> DisplayTrace | None:
        if self._displayed_traces:
            return self._displayed_traces[0]
        sweep = self._current_sweep()
        series = self._current_series()
        if sweep is not None:
            return self._trace_from_sweep(sweep, series.name if series is not None else "", self.sweep_spin.value() - 1)
        return None

    def _threshold_range(self, y) -> tuple[float, float]:
        finite = self._sample_for_control_stats(y)
        if finite.size == 0:
            return -1.0, 1.0
        lo = float(np.nanpercentile(finite, 1))
        hi = float(np.nanpercentile(finite, 99))
        if lo == hi:
            lo, hi = float(np.nanmin(finite)), float(np.nanmax(finite))
        if lo == hi:
            lo, hi = lo - 1.0, hi + 1.0
        pad = 0.10 * (hi - lo)
        return lo - pad, hi + pad


    def _update_threshold_slider_from_trace(self, y) -> None:
        self._set_slider_from_threshold(self.threshold_value())

    def _set_slider_from_threshold(self, threshold: float) -> None:
        trace = self._reference_trace_for_controls()
        if trace is None:
            return
        ymin, ymax = self._threshold_range(trace.y)
        if ymax <= ymin:
            return
        pos = int(round(1000 * (threshold - ymin) / (ymax - ymin)))
        pos = max(0, min(1000, pos))
        self.threshold_slider.blockSignals(True)
        self.threshold_slider.setValue(pos)
        self.threshold_slider.blockSignals(False)

    def _sample_for_control_stats(self, y, max_points: int = 5000):
        """Small finite sample for threshold/slider statistics.

        Full percentile scans on the first displayed trace made the automatic
        load/series-switch path feel choppy, while the Display Current Sweep
        button was fast because it only redrew the trace.
        """
        arr = np.asarray(y, dtype=float)
        if arr.size > max_points:
            step = max(1, int(np.ceil(arr.size / max_points)))
            arr = arr[::step]
        return arr[np.isfinite(arr)]

    @QtCore.Slot()
    def auto_threshold(self) -> None:
        trace = self._reference_trace_for_controls()
        if trace is None:
            sweep = self._current_sweep()
            series = self._current_series()
            if sweep is None:
                return
            trace = self._trace_from_sweep(sweep, series.name if series is not None else "", self.sweep_spin.value() - 1)
        finite = self._sample_for_control_stats(trace.y)
        if finite.size == 0:
            threshold = 0.0
        else:
            median = float(np.nanmedian(finite))
            direction = self.detect_direction_combo.currentText().lower()
            if "above" in direction:
                p = float(np.nanpercentile(finite, 95))
                threshold = median + 0.5 * (p - median)
            else:
                p = float(np.nanpercentile(finite, 5))
                threshold = median + 0.5 * (p - median)
        self.set_threshold_value(threshold)


    def min_spacing_points(self, trace: DisplayTrace | None = None) -> int:
        if trace is None:
            trace = self._reference_trace_for_controls()
        ms = float(self.min_spacing_spin.value())
        dt = trace.sampling_interval if trace is not None else None
        if dt is None or dt <= 0:
            return max(1, int(round(ms)))
        return max(1, int(round((ms / 1000.0) / dt)))

    @QtCore.Slot()
    def update_spacing_readout(self) -> None:
        trace = self._reference_trace_for_controls()
        if trace is None or trace.sampling_interval is None:
            self.spacing_readout.setText("Min spacing conversion: no sampling interval found; using value approximately as points.")
            return
        points = self.min_spacing_points(trace)
        self.spacing_readout.setText(
            f"Min spacing conversion: {self.min_spacing_spin.value():.3f} ms = "
            f"{points} points at dt={trace.sampling_interval:g} s"
        )

    def _direction_for_detection(self, trace: DisplayTrace) -> str:
        txt = self.detect_direction_combo.currentText().lower()
        if txt.startswith("below"):
            return "down"
        if txt.startswith("above"):
            return "up"
        y = np.asarray(trace.y, dtype=float)
        finite = y[np.isfinite(y)]
        baseline = float(np.nanmedian(finite)) if finite.size else 0.0
        return "down" if self.threshold_value() < baseline else "up"

    def _series_traces(self, baseline_subtract_each: bool = False) -> list[DisplayTrace]:
        series = self._current_series()
        if series is None:
            return []
        traces = []
        for i in self._selected_sweep_indices(series):
            sweep = series.sweep(i)
            tr = self._trace_from_sweep(sweep, series.name, i, source="raw")
            if baseline_subtract_each:
                tr = DisplayTrace(
                    x=tr.x,
                    y=baseline_subtract(tr.y),
                    series_name=tr.series_name,
                    sweep_index=tr.sweep_index,
                    display_name=tr.display_name + " baseline-subtracted",
                    sampling_interval=tr.sampling_interval,
                    units=tr.units,
                    source="baseline_subtracted",
                )
            else:
                tr = self._maybe_apply_persistent_baseline(tr)
            traces.append(tr)
        return traces

    def _traces_to_analyze(self) -> list[DisplayTrace]:
        if self.analyze_all_radio.isChecked():
            return self._series_traces(baseline_subtract_each=False)
        if self._displayed_traces:
            return self._displayed_traces
        trace = self._reference_trace_for_controls()
        return [trace] if trace is not None else []

    def _baseline_overlay_traces_fast(self, max_plotted: int = 100, preserve_x=None) -> list[DisplayTrace]:
        """Baseline-subtract selected sweeps for the current series in one vectorized pass.

        The display range for the plotted subset is cached here so later
        Autoscale does not need to rescan trace objects and freeze the UI.
        """
        series = self._current_series()
        if series is None:
            return []
        indices = self._selected_sweep_indices(series)
        if not indices:
            return []

        data = np.asarray(series.data, dtype=float)
        if data.ndim == 1:
            data = data[:, None]
        valid_indices = [i for i in indices if 0 <= i < data.shape[1]]
        if not valid_indices:
            return []

        selected = data[:, valid_indices]
        means = np.nanmean(selected, axis=0, keepdims=True)
        baseline_data = selected - means

        dt = series.sampling_interval or 1.0
        x = np.arange(data.shape[0], dtype=float) * dt

        plotted_cols = min(max_plotted, baseline_data.shape[1])
        self._cached_display_range = self._range_from_xy_matrix(
            x,
            baseline_data[:, :plotted_cols],
            preserve_x=preserve_x,
            units=series.units,
        )

        traces: list[DisplayTrace] = []
        for out_col, sweep_index in enumerate(valid_indices):
            self._baseline_enabled_by_trace_key[self._trace_key(series.name, sweep_index)] = True
            traces.append(
                DisplayTrace(
                    x=x,
                    y=baseline_data[:, out_col],
                    series_name=series.name,
                    sweep_index=sweep_index,
                    display_name=f"{series.name} sweep {sweep_index + 1} baseline-subtracted",
                    sampling_interval=series.sampling_interval,
                    units=series.units,
                    source="baseline_subtracted",
                )
            )
        return traces


    @QtCore.Slot()
    def baseline_subtract_scope(self) -> None:
        """Baseline-subtract the visible/displayed traces without creating a huge UI workload.

        Earlier branches could create baseline-subtracted DisplayTrace objects for
        every selected sweep, store them in `_displayed_traces`, and pass them
        through `_set_displayed_traces()`. That made the plot and Autoscale
        operate on a very large full-resolution trace list and could freeze the
        UI. This method treats Baseline as a display operation: it baseline-
        subtracts only the visible/plotted traces, keeps those as the UI range
        traces, and immediately applies a Y range from the new baseline data.
        """
        saved_view = self._current_view_range()

        source_traces = list(getattr(self, "_range_traces", []) or getattr(self, "_displayed_traces", []) or [])
        if not source_traces:
            source_traces = self._traces_to_analyze()
        if not source_traces:
            return

        # Bound the display workload. Full selected sweeps can be re-overlaid or
        # reprocessed later, but the UI should not be asked to redraw/range-scan
        # thousands of traces from one Baseline click.
        max_show = min(len(source_traces), 100)
        source_traces = source_traces[:max_show]

        out: list[DisplayTrace] = []
        ymins = []
        ymaxs = []
        baseline_offsets: list[float] = []
        already_baseline = bool(source_traces) and all(tr.source == "baseline_subtracted" for tr in source_traces)
        for tr in source_traces:
            self._baseline_enabled_by_trace_key[self._trace_key(tr.series_name, tr.sweep_index)] = True
            if tr.source == "baseline_subtracted":
                y = tr.y
                baseline_offsets.append(0.0)
            else:
                try:
                    offset = float(np.nanmean(np.asarray(tr.y, dtype=float)))
                except Exception:
                    offset = 0.0
                y = baseline_subtract(tr.y)
                baseline_offsets.append(offset)
            out.append(
                DisplayTrace(
                    x=tr.x,
                    y=y,
                    series_name=tr.series_name,
                    sweep_index=tr.sweep_index,
                    display_name=(tr.display_name if tr.source == "baseline_subtracted" else tr.display_name + " baseline-subtracted"),
                    sampling_interval=tr.sampling_interval,
                    units=tr.units,
                    source="baseline_subtracted",
                )
            )
            ys = self._sample_for_range(y)
            if ys.size:
                ymins.append(float(np.nanmin(ys)))
                ymaxs.append(float(np.nanmax(ys)))

        if not out:
            return

        self._display_mode = "baseline_overlay" if len(out) > 1 else "baseline"
        self._displayed_traces = out
        self._range_traces = out
        self._cached_display_range = None
        self._detection_marker_items = []

        self._clear_stimulus_right_axis()
        self._disable_plot_autorange()
        self.plot.clear()
        for tr in out:
            self.plot.plot(tr.x, tr.y)

        if len(out) > 1:
            suffix = "" if len(source_traces) <= max_show else f" first {max_show} of"
            self.plot.setTitle(f"Baseline-subtracted overlay:{suffix} {len(out)} visible sweeps")
        else:
            self.plot.setTitle(out[0].display_name)

        if out:
            self.plot.setLabel("bottom", "Time", units="s")
            self.plot.setLabel("left", out[0].units or "Signal")

        self._readd_detection_windows_to_plot()

        # When the displayed trace is shifted by baseline subtraction, move the
        # threshold by the same offset so it stays in the same relative place on
        # the first visible trace. For overlays, the first visible trace defines
        # the shared threshold reference.
        if not already_baseline and baseline_offsets:
            first_offset = baseline_offsets[0]
            if np.isfinite(first_offset):
                self.set_threshold_value(self.threshold_value() - first_offset, update_line=False)

        self._ensure_threshold_line()
        self.update_spacing_readout()

        # Apply a range from the new baseline-subtracted visible traces. This is
        # the key fix for offset removal: do not preserve the old Y range.
        self._apply_explicit_range(out, preserve_x=saved_view)

        if already_baseline:
            self.results_summary.setText(
                f"Baseline display refreshed for {len(out)} visible trace(s); X range preserved."
            )
        else:
            self.results_summary.setText(
                f"Baseline-subtracted {len(out)} visible trace(s). Autoscale will use only these visible trace(s)."
            )





    def _parse_sweep_selection(self, sweep_count: int) -> list[int]:
        """Return zero-based sweep indices from text like '1-5,8,10-12'.

        Blank means all sweeps for all-series operations.
        """
        text = self.sweep_selection_edit.text().strip()
        if not text:
            return list(range(sweep_count))

        selected: set[int] = set()
        for part in text.replace(" ", "").split(","):
            if not part:
                continue
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                try:
                    start = int(start_s)
                    end = int(end_s)
                except ValueError:
                    continue
                if end < start:
                    start, end = end, start
                for one_based in range(start, end + 1):
                    if 1 <= one_based <= sweep_count:
                        selected.add(one_based - 1)
            else:
                try:
                    one_based = int(part)
                except ValueError:
                    continue
                if 1 <= one_based <= sweep_count:
                    selected.add(one_based - 1)

        return sorted(selected) if selected else list(range(sweep_count))

    def _selected_sweep_indices(self, series) -> list[int]:
        if series is None:
            return []
        return self._parse_sweep_selection(series.sweep_count)

    def _current_x_range(self) -> tuple[float, float] | None:
        trace = self._reference_trace_for_controls()
        if trace is None or trace.x.size == 0:
            return None
        return float(np.nanmin(trace.x)), float(np.nanmax(trace.x))

    @QtCore.Slot()
    def sync_pair_width_to_first_if_needed(self, *args) -> None:
        """Set the paired-window width to the first-window width as a starting point.

        The second width is intentionally editable after this sync.
        """
        if not hasattr(self, "pair_width_ms_spin") or not hasattr(self, "stim_window_width_ms_spin"):
            return
        # If called from the paired-window checkbox, only sync when enabling.
        if args and isinstance(args[0], bool) and not args[0]:
            return
        self.pair_width_ms_spin.blockSignals(True)
        self.pair_width_ms_spin.setValue(float(self.stim_window_width_ms_spin.value()))
        self.pair_width_ms_spin.blockSignals(False)

    @QtCore.Slot(float)
    def frequency_value_changed(self, hz: float) -> None:
        """Update derived frequency/period UI when the manual frequency changes.

        The first detection-window width is set to half the stimulus period.
        If paired windows are enabled, the second-window width follows the first
        window width.
        """
        if hz <= 0:
            return
        period_ms = 1000.0 / float(hz)
        half_period_ms = period_ms / 2.0
        if hasattr(self, "frequency_period_label"):
            self.frequency_period_label.setText(f"Period: {period_ms:.0f} ms; half: {half_period_ms:.0f} ms")
            self.frequency_period_label.setToolTip(
                f"Frequency {hz:.3f} Hz gives a period of {period_ms:.0f} ms. "
                f"Window width is set to half-period: {half_period_ms:.0f} ms."
            )
        if hasattr(self, "stim_window_width_ms_spin"):
            self.stim_window_width_ms_spin.blockSignals(True)
            self.stim_window_width_ms_spin.setValue(half_period_ms)
            self.stim_window_width_ms_spin.blockSignals(False)
        self.sync_pair_width_to_first_if_needed()

    @QtCore.Slot()
    def set_20hz_window_defaults(self) -> None:
        self.stim_frequency_hz_spin.setValue(20.0)
        # frequency_value_changed sets first-window width to half-period (25 ms).
        self.pair_offset_ms_spin.setValue(100.0)
        self.sync_pair_width_to_first_if_needed()
        self.results_summary.setText(
            "20 Hz defaults set: period = 50 ms, first-window width = 25 ms, paired-window gap = 100 ms. "
            "The first-window width follows half of the period when frequency changes."
        )

    @QtCore.Slot()
    def generate_stimulus_windows(self) -> None:
        xr = self._current_x_range()
        if xr is None:
            self.results_summary.setText("Cannot generate windows: no displayed trace.")
            return

        self.clear_detection_windows()

        trace_start, trace_end = xr
        onset_s = float(self.stim_onset_ms_spin.value()) / 1000.0
        width_s = float(self.stim_window_width_ms_spin.value()) / 1000.0
        frequency_hz = float(self.stim_frequency_hz_spin.value())
        period_s = 1.0 / frequency_hz
        # Number of primary windows. If paired window is enabled, one second window is also created for each primary window.
        count = int(self.stim_window_count_spin.value())

        def add_region(start: float, end: float) -> None:
            if start > trace_end:
                return
            end = min(end, trace_end)
            if end <= start:
                return
            region = pg.LinearRegionItem(values=(start, end), orientation="vertical", movable=True)
            region.setZValue(10)
            region.sigRegionChanged.connect(self.update_window_summary)
            self._detection_windows.append(region)
            self.plot.addItem(region)

        paired = self.paired_windows_checkbox.isChecked()
        pair_offset_s = float(self.pair_offset_ms_spin.value()) / 1000.0
        pair_width_s = float(self.pair_width_ms_spin.value()) / 1000.0

        for i in range(count):
            cycle_start = trace_start + onset_s + i * period_s
            add_region(cycle_start, cycle_start + width_s)
            if paired:
                add_region(cycle_start + pair_offset_s, cycle_start + pair_offset_s + pair_width_s)

        self.use_windows_checkbox.setChecked(bool(self._detection_windows))
        self.update_window_summary()
        pair_msg = (
            f", paired offset={self.pair_offset_ms_spin.value():.3f} ms, "
            f"paired width={self.pair_width_ms_spin.value():.3f} ms"
            if paired else ""
        )
        self.results_summary.setText(
            f"Generated {len(self._detection_windows)} detection window(s): "
            f"onset={self.stim_onset_ms_spin.value():.3f} ms, "
            f"frequency={frequency_hz:.3f} Hz, period={period_s*1000:.3f} ms, "
            f"width={self.stim_window_width_ms_spin.value():.3f} ms{pair_msg}."
        )

    @QtCore.Slot()
    def add_detection_window(self) -> None:
        xr = self._current_x_range()
        if xr is None:
            self.results_summary.setText("Cannot add detection window: no displayed trace.")
            return
        xmin, xmax = xr
        width = xmax - xmin
        configured_width = float(self.stim_window_width_ms_spin.value()) / 1000.0 if hasattr(self, "stim_window_width_ms_spin") else 0.0
        if width <= 0:
            start, end = xmin, xmax
        elif configured_width > 0 and configured_width < width:
            center = xmin + 0.50 * width
            start = center - configured_width / 2.0
            end = center + configured_width / 2.0
        else:
            start = xmin + 0.40 * width
            end = xmin + 0.60 * width

        region = pg.LinearRegionItem(values=(start, end), orientation="vertical", movable=True)
        region.setZValue(10)
        region.sigRegionChanged.connect(self.update_window_summary)
        self._detection_windows.append(region)
        self.plot.addItem(region)
        self.use_windows_checkbox.setChecked(True)
        self.update_window_summary()

    @QtCore.Slot()
    def clear_detection_windows(self) -> None:
        for region in list(self._detection_windows):
            try:
                self.plot.removeItem(region)
            except Exception:
                pass
        self._detection_windows = []
        self.use_windows_checkbox.setChecked(False)
        self.update_window_summary()

    def _readd_detection_windows_to_plot(self) -> None:
        for region in self._detection_windows:
            if region not in self.plot.items():
                self.plot.addItem(region)

    def _active_detection_windows(self, trace: DisplayTrace) -> list[tuple[int, float, float]]:
        if not self.use_windows_checkbox.isChecked() or not self._detection_windows:
            if trace.x.size == 0:
                return [(0, 0.0, 0.0)]
            return [(0, float(np.nanmin(trace.x)), float(np.nanmax(trace.x)))]

        windows = []
        for i, region in enumerate(self._detection_windows, start=1):
            a, b = region.getRegion()
            start, end = (float(a), float(b)) if a <= b else (float(b), float(a))
            windows.append((i, start, end))
        return windows

    @QtCore.Slot()
    def update_window_summary(self) -> None:
        if not hasattr(self, "window_summary"):
            return
        if not self._detection_windows:
            text = "No windows. Detection uses full trace."
        else:
            parts = []
            for i, region in enumerate(self._detection_windows, start=1):
                a, b = region.getRegion()
                start, end = (float(a), float(b)) if a <= b else (float(b), float(a))
                parts.append(f"W{i}: {self._fmt_time(start)}-{self._fmt_time(end)} s")
            text = "; ".join(parts)
        self.window_summary.setText(text)
        if hasattr(self, "window_summary_windows_tab"):
            self.window_summary_windows_tab.setText(text)

    def _clear_detection_markers(self) -> None:
        for item in list(getattr(self, "_detection_marker_items", [])):
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self._detection_marker_items = []

    def _add_detection_markers(self, times, amplitudes, first_in_window: bool = False) -> None:
        if first_in_window:
            item = self.plot.plot(
                times,
                amplitudes,
                pen=None,
                symbol="t",
                symbolSize=11,
                symbolBrush=pg.mkBrush(255, 210, 0, 230),
                symbolPen=pg.mkPen(40, 40, 40, 200),
            )
        else:
            item = self.plot.plot(
                times,
                amplitudes,
                pen=None,
                symbol="o",
                symbolSize=7,
                symbolBrush=pg.mkBrush(80, 170, 255, 190),
                symbolPen=pg.mkPen(20, 20, 20, 160),
            )
        self._detection_marker_items.append(item)

    def _plot_mouse_clicked(self, event) -> None:
        """Report the clicked plot coordinate and nearest displayed point/event."""
        try:
            if hasattr(event, "button") and event.button() != QtCore.Qt.LeftButton:
                return
            pos = event.scenePos()
            if not self.plot.sceneBoundingRect().contains(pos):
                return
            point = self.plot.getViewBox().mapSceneToView(pos)
            x = float(point.x())
            y = float(point.y())
        except Exception:
            return

        msg = f"Clicked x={self._fmt_time(x)}, y={self._fmt_value(y)}"

        # Prefer nearest detection event if events exist; otherwise nearest displayed trace sample.
        nearest = None
        try:
            rows = getattr(self, "_last_detection_rows", []) or []
            if rows:
                xr = np.array([float(r.get("time_s", np.nan)) for r in rows], dtype=float)
                yr = np.array([float(r.get("amplitude", np.nan)) for r in rows], dtype=float)
                finite = np.isfinite(xr) & np.isfinite(yr)
                if np.any(finite):
                    view = self.plot.getViewBox().viewRange()
                    xspan = max(abs(float(view[0][1] - view[0][0])), 1e-12)
                    yspan = max(abs(float(view[1][1] - view[1][0])), 1e-12)
                    idxs = np.flatnonzero(finite)
                    dist = ((xr[finite] - x) / xspan) ** 2 + ((yr[finite] - y) / yspan) ** 2
                    k = int(idxs[int(np.argmin(dist))])
                    row = rows[k]
                    nearest = (
                        f"nearest event: x={self._fmt_time(row.get('time_s', 0))}, "
                        f"y={self._fmt_value(row.get('amplitude', 0))}, "
                        f"sweep={row.get('sweep', '')}, window={row.get('window', '')}, event={row.get('event', '')}"
                    )
        except Exception:
            nearest = None

        if nearest is None:
            try:
                traces = list(getattr(self, "_range_traces", []) or getattr(self, "_displayed_traces", []) or [])
                best = None
                view = self.plot.getViewBox().viewRange()
                xspan = max(abs(float(view[0][1] - view[0][0])), 1e-12)
                yspan = max(abs(float(view[1][1] - view[1][0])), 1e-12)
                for tr in traces[:20]:
                    tx = np.asarray(tr.x, dtype=float)
                    ty = np.asarray(tr.y, dtype=float)
                    if tx.size == 0 or ty.size == 0:
                        continue
                    i = int(np.nanargmin(np.abs(tx - x)))
                    if i < 0 or i >= ty.size:
                        continue
                    d = ((float(tx[i]) - x) / xspan) ** 2 + ((float(ty[i]) - y) / yspan) ** 2
                    if best is None or d < best[0]:
                        best = (d, tr, i)
                if best is not None:
                    _, tr, i = best
                    nearest = (
                        f"nearest trace point: x={self._fmt_time(float(tr.x[i]))}, "
                        f"y={self._fmt_value(float(tr.y[i]))}, {tr.display_name}"
                    )
            except Exception:
                nearest = None

        if nearest:
            msg += "; " + nearest
        self.results_summary.setText(msg)


    def _min_peak_delta_value(self) -> float | None:
        value = float(self.min_delta_spin.value())
        return None if value <= 0 else value

    @QtCore.Slot()
    def find_spikes(self) -> None:
        traces = self._traces_to_analyze()
        if not traces:
            self.results_summary.setText("No traces selected for detection.")
            return

        self._clear_detection_markers()
        self.results_table.setRowCount(0)
        self._last_detection_rows = []
        self._last_detection_arrays = {}

        threshold = self.threshold_value()
        rows: list[dict[str, float | int | str | bool | None]] = []
        all_times = []
        all_amplitudes = []
        all_sweeps = []
        all_event_numbers = []
        all_trace_numbers = []
        all_window_numbers = []
        all_isi = []
        all_time_from_window_start = []
        first_window_times = []
        first_window_amplitudes = []

        for trace_number, tr in enumerate(traces, start=1):
            direction = self._direction_for_detection(tr)
            event_counter_for_trace = 0

            for window_number, win_start, win_end in self._active_detection_windows(tr):
                if tr.x.size == 0:
                    continue
                mask = (tr.x >= win_start) & (tr.x <= win_end)
                if not np.any(mask):
                    continue

                x_segment = tr.x[mask]
                y_segment = tr.y[mask]
                original_indices = np.flatnonzero(mask)

                result = detect_threshold_crossings(
                    y_segment,
                    x_segment,
                    threshold=threshold,
                    direction=direction,
                    min_spacing_points=self.min_spacing_points(tr),
                    smoothing_points=int(self.smoothing_spin.value()),
                    min_peak_delta=self._min_peak_delta_value(),
                )

                marker_times = []
                marker_amplitudes = []
                first_marker_times = []
                first_marker_amplitudes = []
                prev_time_in_window = None
                event_counter_for_window = 0

                for idx_local, time_s, amp, cross_t in zip(
                    result["indices"], result["times"], result["amplitudes"], result["crossing_times"]
                ):
                    event_counter_for_trace += 1
                    event_counter_for_window += 1
                    first_in_window = event_counter_for_window == 1
                    idx_abs = int(original_indices[int(idx_local)]) if len(original_indices) else int(idx_local)
                    time_s = float(time_s)
                    amp = float(amp)
                    cross_t = float(cross_t)
                    time_from_win_start = time_s - float(win_start)
                    crossing_from_win_start = cross_t - float(win_start)
                    isi_s = None if prev_time_in_window is None else time_s - float(prev_time_in_window)
                    prev_time_in_window = time_s

                    row = {
                        "source": tr.source,
                        "series": tr.series_name,
                        "sweep": int(tr.sweep_index + 1),
                        "trace": int(trace_number),
                        "window": int(window_number),
                        "window_start_s": float(win_start),
                        "window_end_s": float(win_end),
                        "event": int(event_counter_for_trace),
                        "event_in_window": int(event_counter_for_window),
                        "first_in_window": bool(first_in_window),
                        "index": idx_abs,
                        "time_s": time_s,
                        "time_from_window_start_s": time_from_win_start,
                        "amplitude": amp,
                        "crossing_time_s": cross_t,
                        "crossing_time_from_window_start_s": crossing_from_win_start,
                        "isi_s": isi_s,
                        "threshold": float(threshold),
                        "direction": direction,
                        "display_name": tr.display_name,
                    }
                    rows.append(row)
                    all_times.append(time_s)
                    all_amplitudes.append(amp)
                    all_sweeps.append(int(tr.sweep_index + 1))
                    all_event_numbers.append(int(event_counter_for_trace))
                    all_trace_numbers.append(int(trace_number))
                    all_window_numbers.append(int(window_number))
                    all_time_from_window_start.append(time_from_win_start)
                    all_isi.append(np.nan if isi_s is None else float(isi_s))
                    marker_times.append(time_s)
                    marker_amplitudes.append(amp)
                    if first_in_window:
                        first_window_times.append(time_s)
                        first_window_amplitudes.append(amp)
                        first_marker_times.append(time_s)
                        first_marker_amplitudes.append(amp)

                if marker_times and (self.analyze_displayed_radio.isChecked() or len(traces) <= 100):
                    self._add_detection_markers(np.asarray(marker_times), np.asarray(marker_amplitudes), first_in_window=False)
                    if first_marker_times:
                        self._add_detection_markers(np.asarray(first_marker_times), np.asarray(first_marker_amplitudes), first_in_window=True)

        self._last_detection_rows = rows
        self._last_detection_arrays = {
            "time_s": np.asarray(all_times, dtype=float),
            "time_from_window_start_s": np.asarray(all_time_from_window_start, dtype=float),
            "isi_s": np.asarray(all_isi, dtype=float),
            "amplitude": np.asarray(all_amplitudes, dtype=float),
            "sweep": np.asarray(all_sweeps, dtype=int),
            "event": np.asarray(all_event_numbers, dtype=int),
            "trace": np.asarray(all_trace_numbers, dtype=int),
            "window": np.asarray(all_window_numbers, dtype=int),
            "first_window_time_s": np.asarray(first_window_times, dtype=float),
            "first_window_amplitude": np.asarray(first_window_amplitudes, dtype=float),
        }
        self._populate_results_table(rows)


    def _populate_results_table(self, rows) -> None:
        max_rows_displayed = min(len(rows), 2000)
        self.results_table.setRowCount(max_rows_displayed)

        for r, row in enumerate(rows[:max_rows_displayed]):
            values = [
                row.get("source", ""),
                row.get("series", ""),
                row.get("sweep", ""),
                row.get("window", ""),
                row.get("event", ""),
                row.get("event_in_window", ""),
                self._fmt_time(row.get("time_s", 0)),
                self._fmt_time(row.get("time_from_window_start_s", 0)),
                "" if row.get("isi_s") is None else self._fmt_time(row.get("isi_s", 0)),
                self._fmt_value(row.get("amplitude", 0)),
                self._fmt_time(row.get("crossing_time_s", 0)),
                self._fmt_time(row.get("crossing_time_from_window_start_s", 0)),
                "yes" if row.get("first_in_window") else "",
                row.get("direction", ""),
                self._fmt_time(row.get("window_start_s", 0)),
                self._fmt_time(row.get("window_end_s", 0)),
            ]
            for c, value in enumerate(values):
                self.results_table.setItem(r, c, QtWidgets.QTableWidgetItem(str(value)))

        try:
            self.results_tabs.setCurrentWidget(self.detection_results_tab)
        except Exception:
            pass

        if rows:
            by_sweep = len(set(int(r["sweep"]) for r in rows))
            sources = sorted(set(str(r["source"]) for r in rows))
            first_count = sum(1 for r in rows if r.get("first_in_window"))
            self.results_summary.setText(
                f"Detected {len(rows)} events across {by_sweep} sweep(s); {first_count} first-in-window event(s). "
                f"Source: {', '.join(sources)}. "
                f"CSV includes ISI and window-relative timing."
                + (" Showing first 2000 rows." if len(rows) > max_rows_displayed else "")
            )
        else:
            self.results_summary.setText("Detected 0 events.")


    @QtCore.Slot()
    def clear_detection_results(self) -> None:
        self._clear_detection_markers()
        self._last_detection_rows = []
        self._last_detection_arrays = {}
        self.results_table.setRowCount(0)
        self.results_summary.setText("No detections yet.")

    @QtCore.Slot()
    def export_detection_csv(self) -> None:
        if not self._last_detection_rows:
            self.results_summary.setText("No detection results to export.")
            return
        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save detection results",
            "zphys_detection_results.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not path_str:
            return

        import csv

        fieldnames = [
            "source",
            "series",
            "sweep",
            "trace",
            "window",
            "window_start_s",
            "window_end_s",
            "event",
            "event_in_window",
            "first_in_window",
            "index",
            "time_s",
            "time_from_window_start_s",
            "isi_s",
            "amplitude",
            "crossing_time_s",
            "crossing_time_from_window_start_s",
            "threshold",
            "direction",
            "display_name",
        ]
        with open(path_str, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._last_detection_rows)
        self.results_summary.setText(f"Exported {len(self._last_detection_rows)} events to {path_str}")

    @QtCore.Slot()
    def clear_persistent_baseline(self) -> None:
        self._baseline_enabled_by_trace_key.clear()
        self.results_summary.setText("Persistent baseline subtraction cleared.")
        self.update_plot()

    @QtCore.Slot()
    def show_average(self) -> None:
        series = self._current_series()
        recording = self.state.recording
        if series is not None:
            data = series.data
            avg = average_sweeps(data)
            x = series.sweep(0).timebase()[:avg.size]
            tr = DisplayTrace(
                x=x,
                y=np.asarray(avg, dtype=float),
                series_name=series.name,
                sweep_index=0,
                display_name=f"Average: {series.name}",
                sampling_interval=series.sampling_interval,
                units=series.units,
                source="average",
            )
            self._display_mode = "average"
            self._set_displayed_traces([tr], title=f"Average: {series.name}")
        elif recording is not None and recording.sweeps:
            data = recording.stack_sweeps()
            avg = average_sweeps(data)
            x = recording.sweeps[0].timebase()[:avg.size]
            tr = DisplayTrace(x=x, y=np.asarray(avg, dtype=float), display_name="Average sweep", source="average")
            self._display_mode = "average"
            self._set_displayed_traces([tr], title="Average sweep")

    @QtCore.Slot()
    def show_fft(self) -> None:
        trace = self._reference_trace_for_controls()
        if trace is None:
            return
        if trace.sampling_interval is None:
            self.results_summary.setText("FFT: no sampling interval found for this trace.")
            return
        self._display_mode = "fft"
        freq, amp = fft_area(trace.y, trace.sampling_interval)
        self._clear_stimulus_right_axis()
        self.plot.clear()
        self.plot.plot(freq, amp)
        self.plot.setTitle(f"FFT: {trace.display_name}")
        self.plot.setLabel("bottom", "Frequency", units="Hz")
        self.plot.setLabel("left", "Amplitude")
        self.threshold_line.setVisible(False)
        self._displayed_traces = [
            DisplayTrace(
                x=freq,
                y=amp,
                series_name=trace.series_name,
                sweep_index=trace.sweep_index,
                display_name=f"FFT: {trace.display_name}",
                sampling_interval=None,
                source="fft",
            )
        ]

    @QtCore.Slot()
    def show_concatenated(self) -> None:
        series = self._current_series()
        if series is None:
            return
        self._display_mode = "concat"
        indices = self._selected_sweep_indices(series)
        if not indices:
            self.results_summary.setText("No sweeps selected for concatenation.")
            return

        # Concatenating many sweeps can create a very long vector. Plot and range
        # a display-sized copy so the UI remains responsive.
        sweep_arrays = [np.asarray(series.sweep(i).y, dtype=float) for i in indices]
        y = np.concatenate(sweep_arrays)
        dt = series.sampling_interval
        x = np.arange(y.size) * dt if dt else np.arange(y.size)
        selection_text = self.sweep_selection_edit.text().strip() or "all sweeps"

        dx, dy = self._display_decimated_xy(x, y, max_points=20000)
        tr_display = DisplayTrace(
            x=dx,
            y=dy,
            series_name=series.name,
            sweep_index=0,
            display_name=f"Concatenated sweeps {selection_text}: {series.name}",
            sampling_interval=dt,
            units=series.units,
            source="concatenated_display",
        )

        self._displayed_traces = [tr_display]
        self._range_traces = [tr_display]
        self._cached_display_range = None
        self._detection_marker_items = []

        self._clear_stimulus_right_axis()
        self._disable_plot_autorange()
        self.plot.clear()
        self.plot.plot(dx, dy)
        self.plot.setTitle(f"Concatenated sweeps {selection_text}: {series.name}")
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", series.units or "Signal")
        self._readd_detection_windows_to_plot()

        # Concatenation changes the displayed trace context, so update the
        # threshold from the concatenated display trace before re-adding the line.
        finite = self._sample_for_control_stats(dy)
        if finite.size:
            median = float(np.nanmedian(finite))
            direction = self.detect_direction_combo.currentText().lower()
            if "above" in direction:
                p = float(np.nanpercentile(finite, 95))
                threshold = median + 0.5 * (p - median)
            else:
                p = float(np.nanpercentile(finite, 5))
                threshold = median + 0.5 * (p - median)
            self.set_threshold_value(threshold, update_line=False)

        self._ensure_threshold_line()
        self.update_spacing_readout()
        self._apply_range_from_xy(dx, dy, units=series.units)

        if len(dx) < len(x):
            self.results_summary.setText(
                f"Displayed concatenated sweeps {selection_text} using {len(dx):,} of {len(x):,} points for responsiveness."
            )
        else:
            self.results_summary.setText(f"Displayed concatenated sweeps {selection_text}.")


    @QtCore.Slot()
    def overlay_all_sweeps(self) -> None:
        series = self._current_series()
        if series is None:
            return
        self._display_mode = "overlay"
        traces = self._series_traces(baseline_subtract_each=False)
        self._displayed_traces = traces
        self._detection_marker_items = []
        self._clear_stimulus_right_axis()
        self._disable_plot_autorange()
        self.plot.clear()
        max_sweeps = min(len(traces), 100)
        plotted_traces = traces[:max_sweeps]
        self._range_traces = plotted_traces
        self._cached_display_range = None
        for tr in plotted_traces:
            self.plot.plot(tr.x, tr.y)
        suffix = "" if len(traces) <= max_sweeps else f" first {max_sweeps} of"
        self.plot.setTitle(f"Overlay:{suffix} {len(traces)} sweeps - {series.name}")
        self._ensure_threshold_line()
        self.update_spacing_readout()


    @QtCore.Slot()
    def show_matching_s2(self) -> None:
        """Display the matching simultaneously recorded S2 trace for the current series.

        S2 is treated as a recorded input channel, not the output stimulus waveform.
        If exact matching fails, present a chooser dialog of all S2-like series.
        """
        recording = self.state.recording
        series = self._current_series()
        if recording is None or series is None:
            return

        def as_int(value):
            try:
                return int(value)
            except Exception:
                return None

        def signal_number(s):
            meta_value = as_int(s.metadata.get("signal_number"))
            if meta_value is not None:
                return meta_value
            m = re.search(r"(?:^|_)S(\d+)(?:_|$)", s.name)
            return int(m.group(1)) if m else None

        def routine_number(s):
            meta_value = as_int(s.metadata.get("routine_number"))
            if meta_value is not None:
                return meta_value
            m = re.search(r"(?:^|_)R(\d+)(?:_|$)", s.name)
            if m:
                return int(m.group(1))
            m = re.search(r"R(\d+)_S\d+", s.name)
            return int(m.group(1)) if m else None

        def routine_name(s):
            meta_value = s.metadata.get("routine_name")
            if meta_value:
                return str(meta_value)
            m = re.search(r"R\d+_S\d+_(.*)$", s.name)
            return m.group(1) if m else ""

        def is_s2_like(s):
            return signal_number(s) == 2 or bool(re.search(r"(?:^|_)S2(?:_|$)", s.name))

        def display(stim_series, reason):
            idx = current_sweep_index(self.sweep_spin.value(), stim_series.sweep_count)
            sweep = stim_series.sweep(idx)
            self._display_mode = "single"
            tr = self._trace_from_sweep(sweep, stim_series.name, idx, source="s2")
            self._set_displayed_traces([tr], title=f"Recorded S2: {sweep.name}")
            self._request_full_autoscale()
            self.results_summary.setText(
                f"Displayed recorded S2: {stim_series.name}, sweep {idx + 1}. "
                f"From {series.name}. Match: {reason}."
            )

        if is_s2_like(series):
            display(series, "current selected S2 series")
            return

        cur_rnum = routine_number(series)
        cur_rname = routine_name(series)
        s2_series = [s for s in recording.series if s is not series and is_s2_like(s)]

        # 1. Same routine number and S2-like.
        for s in s2_series:
            if cur_rnum is not None and routine_number(s) == cur_rnum:
                display(s, "same routine number")
                return

        # 2. Same routine name and S2-like.
        for s in s2_series:
            if cur_rname and routine_name(s) == cur_rname:
                display(s, "same routine name")
                return

        # 3. Direct S1 to S2 name substitution.
        expected_names = {
            re.sub(r"(?<=_)S1(?=_|$)", "S2", series.name),
            re.sub(r"S1(?=_|$)", "S2", series.name),
        }
        for s in recording.series:
            if s is not series and s.name in expected_names:
                display(s, "S1 to S2 name substitution")
                return

        # 4. Manual chooser fallback for any S2-like series.
        if s2_series:
            names = [s.name for s in s2_series]
            item, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Choose S2 series",
                f"No exact S2 match found for {series.name}. Choose recorded S2 series:",
                names,
                0,
                False,
            )
            if ok and item:
                for s in s2_series:
                    if s.name == item:
                        display(s, "manual chooser")
                        return
            self.results_summary.setText(f"S2 display cancelled. Found {len(s2_series)} S2-like candidates.")
            return

        self.results_summary.setText(
            f"No recorded S2 candidates found for {series.name}. "
            "Expected names usually look like R##_S2_RoutineName."
        )

    def _stimulus_series_candidates(self) -> list:
        recording = self.state.recording
        if recording is None:
            return []
        candidates = recording.metadata.get("stimulus_series", []) or []
        return list(candidates)

    def _stimulus_candidate_description(self, stim) -> str:
        name = str(stim.name)
        signal_name = str(stim.metadata.get("signal_name") or "")
        source = str(stim.metadata.get("source") or stim.metadata.get("igor_name") or "")
        synthetic = bool(stim.metadata.get("synthetic_stimulus"))
        synthetic_kind = str(stim.metadata.get("synthetic_kind") or "")
        try:
            arr = np.asarray(stim.data, dtype=float)
            finite = arr[np.isfinite(arr)]
            if finite.size:
                ymin = float(np.nanmin(finite)); ymax = float(np.nanmax(finite))
                flat = ymin == ymax
                rng = f"range {ymin:.4g}..{ymax:.4g}"
            else:
                flat = True; rng = "empty"
        except Exception:
            flat = False; rng = "range unknown"
        tags = []
        lname = f"{name} {signal_name}".lower()
        if any(tok in lname for tok in ("digout", "ttl", "digital", "word")):
            tags.append("digital")
        if any(tok in lname for tok in ("stimout", "auxout", "dac", "analog")):
            tags.append("analog")
        if flat:
            tags.append("flat")
        if stim.metadata.get("preview_only") or stim.metadata.get("not_authoritative_stimulus"):
            tags.append("preview only / not authoritative")
        if synthetic:
            tags.append(f"synthetic:{synthetic_kind or 'fallback'}")
        shape = getattr(stim, "data", np.array([])).shape
        return f"{name} | {signal_name or 'no signal name'} | {shape} | {rng} | {', '.join(tags) or 'stored'} | {source}"

    def _trusted_automatic_stimulus_candidates(self, candidates: list, routine_name: str) -> list:
        """Return only real stored/recorded output candidates, not previews or reconstructions."""
        trusted = []
        for stim in candidates:
            metadata = getattr(stim, "metadata", {}) or {}
            if metadata.get("synthetic_stimulus") or metadata.get("preview_only") or metadata.get("not_authoritative_stimulus"):
                continue
            signal_name = str(metadata.get("signal_name") or "").lower()
            name = str(getattr(stim, "name", "")).lower()
            source = str(metadata.get("source") or "").lower()
            lname = f"{name} {signal_name} {source}"
            looks_like_output = any(tok in lname for tok in (
                "stimout", "auxout", "dac", "digout", "ttl", "digital", "word",
                "virtual output", "stored output", "recorded output", "command"
            ))
            try:
                finite = np.asarray(stim.data, dtype=float)
                finite = finite[np.isfinite(finite)]
                is_flat = (not finite.size) or float(np.nanmax(finite)) == float(np.nanmin(finite))
            except Exception:
                is_flat = False
            if looks_like_output and not is_flat:
                trusted.append(stim)
        return trusted


    def _best_stimulus_series_for_current(self):
        candidates = self._stimulus_series_candidates()
        if not candidates:
            return None
        selected_name = getattr(self, "_selected_stimulus_series_name", None)
        if selected_name:
            for stim in candidates:
                if stim.name == selected_name:
                    return stim
        current = self._current_series()
        if current is None:
            return candidates[0]
        routine_name = str(current.metadata.get("routine_name") or "").lower()
        point_count = int(current.point_count)
        trusted_candidates = self._trusted_automatic_stimulus_candidates(candidates, routine_name)
        if not trusted_candidates:
            return None
        def score(stim):
            signal_name = str(stim.metadata.get("signal_name") or "").lower()
            name = str(stim.name).lower()
            length_score = abs(int(stim.point_count) - point_count)
            kind_score = 0
            is_digital = any(tok in signal_name or tok in name for tok in ("digout", "ttl", "digital", "word"))
            is_analog = any(tok in signal_name or tok in name for tok in ("stimout", "auxout", "dac", "analog"))
            if "light" in routine_name and is_digital:
                kind_score -= 1000
            elif is_analog:
                kind_score -= 500
            return (length_score + kind_score, length_score, stim.name)
        return sorted(trusted_candidates, key=score)[0]

    @QtCore.Slot()
    def choose_stimulus_source(self) -> None:
        candidates = self._stimulus_series_candidates()
        if not candidates:
            self.results_summary.setText("No stimulus candidates found in this recording.")
            return
        labels = [self._stimulus_candidate_description(stim) for stim in candidates]
        current_label = 0
        selected = getattr(self, "_selected_stimulus_series_name", None)
        if selected:
            for i, stim in enumerate(candidates):
                if stim.name == selected:
                    current_label = i
                    break
        item, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Choose stored output/stimulus source",
            "Choose a stored output/stimulus candidate to display or overlay:\nPreview-only AppControl sources are shown for inspection but are not treated as authoritative.",
            labels,
            current_label,
            False,
        )
        if not ok or not item:
            return
        idx = labels.index(item)
        self._selected_stimulus_series_name = candidates[idx].name
        tr = self._stimulus_trace(candidates[idx])
        if tr is not None:
            self._display_mode = "stimulus"
            self._set_displayed_traces([tr], title=tr.display_name, left_label=tr.units or "Stimulus")
            self._request_full_autoscale()
            self.results_summary.setText(
                "Selected stimulus source: " + self._stimulus_candidate_description(candidates[idx])
            )

    def _stimulus_trace(self, stim_series=None) -> DisplayTrace | None:
        if stim_series is None:
            stim_series = self._best_stimulus_series_for_current()
        if stim_series is None:
            return None
        idx = 0
        if stim_series.sweep_count > 1:
            idx = current_sweep_index(self.sweep_spin.value(), stim_series.sweep_count)
        sweep = stim_series.sweep(idx)
        tr = self._trace_from_sweep(sweep, stim_series.name, idx, source="stimulus")
        tr.display_name = f"Stored output/stimulus: {stim_series.name}"
        return tr

    @QtCore.Slot()
    def show_matching_stimulus(self) -> None:
        """Display a real stored/recorded output waveform when one is available."""
        tr = self._stimulus_trace()
        if tr is None:
            count = len(self._stimulus_series_candidates())
            if count:
                self.results_summary.setText(
                    f"No trusted stored/recorded output waveform was found for this routine. Found {count} preview/candidate source(s), "
                    "but SutterPatch says AppControl objects should not be used as dataset stimulus data. "
                    "For old files, open the file in SutterPatch and generate/store a virtual output signal; "
                    "for future files, record the stimulus/output during acquisition."
                )
            else:
                self.results_summary.setText(
                    "No stored stimulus/output waveform was found in this PXP file. "
                    "For old files, open the file in SutterPatch and generate/store a virtual output signal; "
                    "for future files, record the stimulus/output during acquisition."
                )
            return
        self._display_mode = "stimulus"
        self._set_displayed_traces([tr], title=tr.display_name, left_label=tr.units or "Output")
        self._request_full_autoscale()
        self.results_summary.setText(
            f"Displayed stored output/stimulus waveform: {tr.series_name}. "
            "S2 remains a simultaneously recorded input signal, not the stimulus source."
        )


    @QtCore.Slot()
    def overlay_matching_stimulus(self) -> None:
        """Overlay the PXP stimulus/output preview on the selected sweep."""
        series = self._current_series()
        if series is None:
            self.results_summary.setText("No recorded sweep is selected for stimulus overlay.")
            return

        idx = current_sweep_index(self.sweep_spin.value(), series.sweep_count)
        sweep = series.sweep(idx)
        sig = series.metadata.get("signal_number")
        try:
            sig = int(sig) if sig is not None else None
        except Exception:
            sig = None
        source = "s2" if sig == 2 or re.search(r"(?:^|_)S2(?:_|$)", series.name) else "raw"
        base = self._trace_from_sweep(sweep, series.name, idx, source=source)
        base = self._maybe_apply_persistent_baseline(base)

        stim = self._stimulus_trace()
        if stim is None:
            self.results_summary.setText(
                "No trusted stored/recorded output waveform found to overlay. "
                "SutterPatch says AppControl previews are not authoritative stimulus data; "
                "generate/store a virtual output in SutterPatch for old files or record the output during acquisition."
            )
            return

        self._display_mode = "stimulus_overlay"
        self._set_displayed_traces([base, stim], title=f"{base.display_name} + stored output/stimulus preview")
        self._request_full_autoscale()
        self.results_summary.setText(
            f"Overlayed stored output/stimulus preview {stim.series_name} in orange on a separate right Y axis with {base.display_name}. "
            "The selected recorded sweep remains on the left Y axis."
        )

    @QtCore.Slot()
    def show_event_histogram(self) -> None:
        if not self._last_detection_rows:
            self.results_summary.setText("Run Find Spikes / Events first.")
            return

        # ISI histogram: compute spike_time(n+1) - spike_time(n) within each
        # logical detection group so intervals do not cross traces, sweeps, or
        # windows. Use rows rather than the flat time array because the rows keep
        # the trace/sweep/window identity.
        groups: dict[tuple, list[float]] = {}
        for row in self._last_detection_rows:
            try:
                t = float(row.get("time_s", np.nan))
            except Exception:
                continue
            if not np.isfinite(t):
                continue
            key = (
                row.get("source", ""),
                row.get("series", ""),
                row.get("sweep", ""),
                row.get("trace", ""),
                row.get("window", ""),
            )
            groups.setdefault(key, []).append(t)

        isi_values = []
        contributing_groups = 0
        for values in groups.values():
            if len(values) < 2:
                continue
            arr = np.sort(np.asarray(values, dtype=float))
            diffs = np.diff(arr)
            diffs = diffs[np.isfinite(diffs) & (diffs >= 0)]
            if diffs.size:
                isi_values.extend(diffs.tolist())
                contributing_groups += 1

        intervals = np.asarray(isi_values, dtype=float)
        if intervals.size == 0:
            self.results_summary.setText("Need at least two detected events in the same trace/sweep/window to plot ISI.")
            return

        # Avoid numpy's open-ended "auto" bin count on large detections; too many
        # bars can make the plot sluggish or appear blank/off-scale.
        if intervals.size == 1:
            t0 = float(intervals[0])
            pad = max(abs(t0) * 0.1, 0.001)
            edges = np.array([max(0.0, t0 - pad), t0 + pad], dtype=float)
            if edges[0] == edges[1]:
                edges = np.array([0.0, 0.001], dtype=float)
        else:
            tmin = float(np.nanmin(intervals))
            tmax = float(np.nanmax(intervals))
            if not np.isfinite(tmin) or not np.isfinite(tmax) or tmin == tmax:
                pad = max(abs(tmin) * 0.1, 0.001)
                tmin, tmax = max(0.0, tmin - pad), tmax + pad
            bin_count = int(min(max(10, np.sqrt(intervals.size)), 100))
            edges = np.linspace(tmin, tmax, bin_count + 1)

        counts, edges = np.histogram(intervals, bins=edges)
        centers = (edges[:-1] + edges[1:]) / 2.0
        widths = np.diff(edges)
        width = float(np.nanmedian(widths)) if widths.size else 1.0
        if not np.isfinite(width) or width <= 0:
            width = 1.0

        self._display_mode = "hist"
        self._displayed_traces = []
        self._range_traces = []
        self._cached_display_range = None
        self._detection_marker_items = []

        self._clear_stimulus_right_axis()
        self._disable_plot_autorange()
        self.plot.clear()

        bg = pg.BarGraphItem(
            x=centers,
            height=counts,
            width=0.9 * width,
            brush=pg.mkBrush(120, 160, 220, 180),
            pen=pg.mkPen(220, 220, 220, 120),
        )
        self.plot.addItem(bg)
        self.plot.setTitle("Inter-spike interval (ISI) histogram")
        self.plot.setLabel("bottom", "ISI", units="s")
        self.plot.setLabel("left", "Count")
        self.threshold_line.setVisible(False)

        xmin = float(edges[0])
        xmax = float(edges[-1])
        if xmin == xmax:
            xmin -= 0.5
            xmax += 0.5
        xpad = 0.02 * (xmax - xmin) if xmax > xmin else 0.001
        ymax = int(np.nanmax(counts)) if counts.size else 1
        ymax = max(1, ymax)
        try:
            self.plot.setXRange(max(0.0, xmin - xpad), xmax + xpad, padding=0)
            self.plot.setYRange(0, ymax * 1.15, padding=0)
        except Exception:
            pass

        mean_isi = float(np.nanmean(intervals))
        self.results_summary.setText(
            f"Displayed ISI histogram for {intervals.size} interval(s) from {contributing_groups} trace/window group(s); mean ISI {self._fmt_time(mean_isi)}."
        )


    def _current_view_range(self):
        try:
            view = self.plot.getViewBox().viewRange()
            return (tuple(view[0]), tuple(view[1]))
        except Exception:
            return None

    def _restore_x_range(self, saved_range) -> None:
        if not saved_range:
            return
        try:
            (xmin, xmax), _yr = saved_range
            if np.isfinite(xmin) and np.isfinite(xmax) and xmin < xmax:
                self.plot.setXRange(float(xmin), float(xmax), padding=0)
        except Exception:
            pass

    def _autoscale_y_for_current_x(self, saved_range=None) -> None:
        """Autoscale Y while preserving the current X/time window."""
        if not self._displayed_traces:
            return

        if saved_range:
            (xmin, xmax), _yr = saved_range
        else:
            current = self._current_view_range()
            if current:
                (xmin, xmax), _yr = current
            else:
                xmin = xmax = None

        ys = []
        for tr in self._displayed_traces:
            x = np.asarray(tr.x, dtype=float) if tr.x is not None else np.array([])
            y = np.asarray(tr.y, dtype=float) if tr.y is not None else np.array([])
            if not len(y):
                continue
            if y.size > 20000:
                step = max(1, int(np.ceil(y.size / 20000)))
                y = y[::step]
                if len(x) == len(tr.y):
                    x = x[::step]
            mask = np.isfinite(y)
            if len(x) == len(y) and xmin is not None and xmax is not None and np.isfinite(xmin) and np.isfinite(xmax):
                mask = mask & np.isfinite(x) & (x >= xmin) & (x <= xmax)
            if np.any(mask):
                ys.append(y[mask])

        if not ys:
            return

        y_all = np.concatenate(ys)
        if y_all.size == 0:
            return

        ymin, ymax = float(np.nanmin(y_all)), float(np.nanmax(y_all))
        if ymin == ymax:
            ymin -= 0.5
            ymax += 0.5
        ypad = 0.08 * (ymax - ymin)
        self.plot.setYRange(ymin - ypad, ymax + ypad, padding=0)
        if saved_range:
            self._restore_x_range(saved_range)


    def _fp_settings(self) -> FieldPotentialSettings:
        return FieldPotentialSettings(
            stimulus_onset_s=float(self.fp_stim_onset_spin.value()),
            stimulus_length_s=float(self.fp_stim_length_spin.value()),
            search_offset_s=float(self.fp_search_offset_spin.value()),
            rms_window_s=float(self.fp_rms_window_spin.value()),
            rms_sigma_multiplier=float(self.fp_rms_sigma_spin.value()),
            baseline_subtract=bool(self.fp_baseline_checkbox.isChecked()),
        )

    def _fp_selected_traces(self, current_only: bool = False) -> list[DisplayTrace]:
        series = self._current_series()
        if series is None:
            tr = self._reference_trace_for_controls()
            return [tr] if tr is not None else []
        if current_only:
            idx = current_sweep_index(self.sweep_spin.value(), series.sweep_count)
            return [self._trace_from_sweep(series.sweep(idx), series.name, idx, source="fp")]
        traces = []
        for idx in self._selected_sweep_indices(series):
            traces.append(self._trace_from_sweep(series.sweep(idx), series.name, idx, source="fp"))
        return traces

    def _clear_fp_markers(self) -> None:
        for item in list(getattr(self, "_fp_marker_items", [])):
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self._fp_marker_items = []

    def _fp_add_marker(self, x, y, label: str, symbol: str, brush) -> None:
        if x is None or y is None:
            return
        try:
            if not (np.isfinite(float(x)) and np.isfinite(float(y))):
                return
            item = self.plot.plot(
                [float(x)], [float(y)], pen=None, symbol=symbol, symbolSize=12,
                symbolBrush=brush, symbolPen=pg.mkPen(30, 30, 30, 220),
                name=label,
            )
            self._fp_marker_items.append(item)
            text = pg.TextItem(label, anchor=(0, 1))
            text.setPos(float(x), float(y))
            self.plot.addItem(text)
            self._fp_marker_items.append(text)
        except Exception:
            pass

    def _fp_plot_result_markers(self, row: dict) -> None:
        self._clear_fp_markers()
        self._fp_add_marker(row.get("onset_time_s"), row.get("onset_y"), "onset", "o", pg.mkBrush(255, 210, 0, 230))
        self._fp_add_marker(row.get("peak_time_s"), row.get("peak_y"), "peak", "t", pg.mkBrush(80, 220, 120, 230))
        self._fp_add_marker(row.get("trough_time_s"), row.get("trough_y"), "trough", "t1", pg.mkBrush(255, 120, 120, 230))
        # Return Y is not part of the Igor result table; interpolate from the displayed trace when possible.
        rt = row.get("return_time_s")
        ry = None
        try:
            traces = getattr(self, "_displayed_traces", []) or []
            if traces and np.isfinite(float(rt)):
                tr = traces[0]
                tx = np.asarray(tr.x, dtype=float)
                ty = np.asarray(tr.y, dtype=float)
                if tx.size and ty.size:
                    ry = float(np.interp(float(rt), tx, ty))
        except Exception:
            ry = None
        self._fp_add_marker(rt, ry, "return", "s", pg.mkBrush(120, 180, 255, 230))

    def _fp_populate_table(self) -> None:
        rows = self._last_fp_rows
        self.fp_results_table.setRowCount(len(rows))
        columns = [
            "source", "sweep", "stim_to_peak_s", "fp_latency_s", "fp_amplitude", "fp_length_s",
            "onset_time_s", "onset_y", "peak_time_s", "peak_y", "trough_time_s", "trough_y",
            "return_time_s", "status",
        ]
        for r, row in enumerate(rows):
            for c, key in enumerate(columns):
                val = row.get(key, "")
                if isinstance(val, float):
                    if "time" in key or key.endswith("_s") or key == "fp_latency_s" or key == "fp_length_s":
                        val = self._fmt_time(val) if np.isfinite(val) else ""
                    else:
                        val = self._fmt_value(val) if np.isfinite(val) else ""
                self.fp_results_table.setItem(r, c, QtWidgets.QTableWidgetItem(str(val)))
        self.results_summary.setText(f"FP analysis has {len(rows)} row(s).")
        try:
            self.results_tabs.setCurrentWidget(self.fp_results_tab)
        except Exception:
            pass

    def _fp_analyze_traces(self, traces: list[DisplayTrace]) -> None:
        if not traces:
            self.results_summary.setText("No traces selected for field-potential analysis.")
            return
        settings = self._fp_settings()
        rows = []
        for tr in traces:
            res = analyze_field_potential(
                tr.x, tr.y, settings,
                source=tr.series_name or tr.source,
                sweep=int(tr.sweep_index + 1),
                display_name=tr.display_name,
            )
            row = result_to_row(res)
            row["_trace_series_name"] = tr.series_name
            row["_trace_sweep_index"] = int(tr.sweep_index)
            rows.append(row)
        self._last_fp_rows = rows
        self._fp_populate_table()
        if rows:
            self.fp_show_result_row(0)
            ok_count = sum(1 for r in rows if str(r.get("status", "")).startswith("OK"))
            self.results_summary.setText(f"Field-potential analysis complete: {len(rows)} sweep(s), {ok_count} OK.")

    @QtCore.Slot()
    def fp_analyze_current_sweep(self) -> None:
        self._fp_analyze_traces(self._fp_selected_traces(current_only=True))

    @QtCore.Slot()
    def fp_analyze_selected_sweeps(self) -> None:
        self._fp_analyze_traces(self._fp_selected_traces(current_only=False))

    def fp_show_result_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._last_fp_rows):
            return
        row = self._last_fp_rows[row_index]
        series_name = row.get("_trace_series_name", "")
        sweep_index = int(row.get("_trace_sweep_index", int(row.get("sweep", 1)) - 1))
        series = None
        for s in getattr(self, "_available_series", []):
            if s.name == series_name:
                series = s
                break
        if series is None:
            series = self._current_series()
        if series is None or not (0 <= sweep_index < series.sweep_count):
            self.results_summary.setText("Could not locate the source sweep for the selected FP row.")
            return
        tr = self._trace_from_sweep(series.sweep(sweep_index), series.name, sweep_index, source="fp")
        settings = self._fp_settings()
        if settings.baseline_subtract:
            y, _ = preprocess_sweep(tr.y, tr.x, settings)
            tr = DisplayTrace(
                x=tr.x, y=y, series_name=tr.series_name, sweep_index=tr.sweep_index,
                display_name=tr.display_name + " FP baseline-subtracted",
                sampling_interval=tr.sampling_interval, units=tr.units, source="fp",
            )
        self._display_mode = "field_potential"
        self._set_displayed_traces([tr], title=f"Field potential review: {tr.display_name}", left_label=tr.units or "Signal")
        self._fp_plot_result_markers(row)
        self.results_summary.setText(
            f"FP row {row_index + 1}: latency {self._fmt_time(row.get('fp_latency_s', np.nan))}, "
            f"amplitude {self._fmt_value(row.get('fp_amplitude', np.nan))}, status {row.get('status', '')}"
        )
        try:
            self.tabs.setCurrentWidget(self.field_potential_tab)
        except Exception:
            pass

    @QtCore.Slot()
    def fp_show_selected_result(self) -> None:
        row = self.fp_results_table.currentRow()
        if row < 0:
            row = 0
        self.fp_show_result_row(row)

    @QtCore.Slot()
    def fp_clear_results(self) -> None:
        self._clear_fp_markers()
        self._last_fp_rows = []
        self.fp_results_table.setRowCount(0)
        self.results_summary.setText("Cleared field-potential results.")

    @QtCore.Slot()
    def fp_export_csv(self) -> None:
        if not self._last_fp_rows:
            self.results_summary.setText("No field-potential results to export.")
            return
        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save field-potential results", "zphys_field_potential_results.csv", "CSV files (*.csv);;All files (*)"
        )
        if not path_str:
            return
        import csv
        fieldnames = [
            "source", "sweep", "stim_to_peak_s", "fp_latency_s", "fp_amplitude", "fp_length_s",
            "onset_time_s", "onset_y", "peak_time_s", "peak_y", "trough_time_s", "trough_y",
            "return_time_s", "status", "display_name",
        ]
        with open(path_str, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self._last_fp_rows)
        self.results_summary.setText(f"Exported {len(self._last_fp_rows)} FP rows to {path_str}")


    @QtCore.Slot()
    def autoscale_displayed_traces(self) -> None:
        """Autoscale visible traces without scanning hidden/full baseline traces."""
        traces = list(getattr(self, "_range_traces", []) or getattr(self, "_displayed_traces", []) or [])
        if traces:
            traces = traces[:100]
        if not traces and not getattr(self, "_cached_display_range", None):
            self._disable_plot_autorange()
            self.results_summary.setText("No displayed traces to autoscale.")
            return
        self._apply_cached_or_explicit_range(traces)
        hidden = max(0, len(getattr(self, "_displayed_traces", []) or []) - len(traces))
        if hidden > 0:
            self.results_summary.setText(f"Autoscaled visible traces; {hidden} additional trace(s) not scanned for display speed.")
        else:
            self.results_summary.setText("Autoscaled displayed traces.")


    @QtCore.Slot()
    def clear_plot(self) -> None:
        self._clear_stimulus_right_axis()
        self._clear_fp_markers()
        self.plot.clear()
        self._detection_marker_items = []
        self._detection_windows = []
        self.update_window_summary()
        self.threshold_line.setVisible(False)
        self._displayed_traces = []
        self._display_mode = "single"

    def _set_file_tools_output(self, text: str) -> None:
        """Write File Tools button output inside the File Tools tab."""
        if hasattr(self, "file_tools_output"):
            self.file_tools_output.setPlainText(text)
            try:
                self.tabs.setCurrentWidget(self.file_tab)
            except Exception:
                pass
        else:
            self.results_summary.setText(text)

    @QtCore.Slot()
    def show_metadata(self) -> None:
        recording = self.state.recording
        if recording is None:
            return

        series = self._current_series()
        lines = [
            f"File: {recording.path}",
            f"Format: {recording.source_format}",
            f"Series count: {len(recording.series)}",
            f"Sweep count: {recording.sweep_count}",
            f"Stored output/stimulus preview series: {len(recording.metadata.get('stimulus_series', []) or [])}",
        ]
        if series is not None:
            lines.extend([
                "",
                f"Current series: {series.name}",
                f"Shape: {series.data.shape}",
                f"Sampling interval: {series.sampling_interval}",
                f"Units: {series.units}",
                f"Routine #: {series.metadata.get('routine_number')}",
                f"Signal #: S{series.metadata.get('signal_number')}",
                f"Routine name: {series.metadata.get('routine_name')}",
            ])

        report = recording.metadata.get("parse_report")
        if report:
            lines.extend(["", f"PXP parse mode: {report.get('mode')}", f"Skipped records: {report.get('records_skipped')}"])

        self._set_file_tools_output("\n".join(lines))

    @QtCore.Slot()
    def show_data_storage(self) -> None:
        self._set_file_tools_output(
            "Loaded data are stored in self.state.recording.\n"
            "SutterPatch waves are self.state.recording.series.\n"
            "Each Series has raw NumPy data in series.data with rows=time points and columns=sweeps.\n"
            "Displayed/processed traces are stored in self._displayed_traces.\n"
            "Persistent baseline flags are stored in self._baseline_enabled_by_trace_key.\n"
            "Detection windows/cursor pairs are stored in self._detection_windows.\n"
            "Detected events are stored in self._last_detection_rows and self._last_detection_arrays."
        )


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
