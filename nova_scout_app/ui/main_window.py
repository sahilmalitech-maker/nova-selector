from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
    QSpinBox,
)

from nova_scout_app.auth.models import AuthUser
from nova_scout_app.constants import APP_TITLE
from nova_scout_app.models import MatchResult, PhotoSelectionResult, ProcessingOptions
from nova_scout_app.services.file_ops import validate_folder_pair
from nova_scout_app.services.text_processing import parse_queries
from nova_scout_app.ui.dialogs import HelpDialog
from nova_scout_app.ui.photo_results import PhotoSelectionResultsWindow
from nova_scout_app.ui.theme import apply_app_theme, build_stylesheet
from nova_scout_app.ui.widgets import (
    AnimatedButton,
    BackdropWidget,
    GlassCard,
    PathDropLineEdit,
    ReferenceListWidget,
    SmoothProgressBar,
    SpinnerWidget,
    StatTile,
)
from nova_scout_app.workers.ocr_worker import OCRThread
from nova_scout_app.workers.photo_selection_worker import PhotoSelectionThread
from nova_scout_app.workers.processing_worker import ProcessingThread


class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1320, 860)
        self.resize(1460, 920)

        self.worker: ProcessingThread | None = None
        self.photo_worker: PhotoSelectionThread | None = None
        self.ocr_thread: OCRThread | None = None
        self.photo_results_window: PhotoSelectionResultsWindow | None = None
        self.last_report_text = ""
        self._current_user_name = "Nova Scout"
        self._current_user_email = "local-photographer"

        self.avatar_network = QNetworkAccessManager(self)
        self.avatar_network.finished.connect(self._on_avatar_reply)

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        root = BackdropWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        header_card = GlassCard(
            "AI-Powered Image Retrieval",
            "Fuzzy filename search, OCR-assisted text capture, and visual similarity matching in one premium desktop workflow.",
        )
        header_row = QHBoxLayout()
        header_row.setSpacing(20)

        title_column = QVBoxLayout()
        brand = QLabel(APP_TITLE)
        brand.setObjectName("HeroTitle")
        subtitle = QLabel(
            "Search thousands of assets by text, screenshot, or visual reference while keeping the interface fast and polished."
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        title_column.addWidget(brand)
        title_column.addWidget(subtitle)
        title_column.addStretch(1)

        header_row.addLayout(title_column, 1)
        header_row.addWidget(self._build_account_panel(), 0, Qt.AlignmentFlag.AlignTop)
        header_card.content_layout.addLayout(header_row)
        layout.addWidget(header_card)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(18)

        left_layout.addWidget(self._build_folders_card())
        left_layout.addWidget(self._build_best_photo_card())
        left_layout.addWidget(self._build_query_card())
        left_layout.addWidget(self._build_reference_card())
        left_layout.addWidget(self._build_options_card())
        left_layout.addWidget(self._build_actions_card())
        left_layout.addStretch(1)

        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([760, 560])

        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _build_account_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("UserPanel")
        panel.setMinimumWidth(320)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.user_avatar_label = self._create_avatar_label(58)

        text_column = QVBoxLayout()
        text_column.setSpacing(4)

        caption = QLabel("Google Session")
        caption.setObjectName("UserPanelCaption")

        self.user_name_label = QLabel("Ready to authenticate")
        self.user_name_label.setObjectName("UserNameLabel")
        self.user_name_label.setWordWrap(True)

        self.user_email_label = QLabel("Workspace will load after sign-in")
        self.user_email_label.setObjectName("UserMetaLabel")
        self.user_email_label.setWordWrap(True)

        self.user_provider_label = QLabel("Provider: Google Sign-In")
        self.user_provider_label.setObjectName("UserMetaLabel")
        self.user_provider_label.setWordWrap(True)

        text_column.addWidget(caption)
        text_column.addWidget(self.user_name_label)
        text_column.addWidget(self.user_email_label)
        text_column.addWidget(self.user_provider_label)

        self.logout_button = AnimatedButton("Logout")
        self.logout_button.clicked.connect(self.logout_requested.emit)

        layout.addWidget(self.user_avatar_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_column, 1)
        layout.addWidget(self.logout_button, 0, Qt.AlignmentFlag.AlignBottom)
        return panel

    def _build_folders_card(self) -> QWidget:
        card = GlassCard(
            "1. Folder Setup",
            "Choose the source library. The destination folder is only needed when copying Smart Match results.",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        source_label = QLabel("Source Folder")
        self.source_edit = PathDropLineEdit(folder_only=True)
        self.source_edit.setPlaceholderText("Drop or browse to the folder containing your full image library")
        source_button = AnimatedButton("Browse")
        source_button.clicked.connect(self.select_source_folder)

        destination_label = QLabel("Destination Folder")
        self.destination_edit = PathDropLineEdit(folder_only=True)
        self.destination_edit.setPlaceholderText("Drop or browse to the folder where matches should be copied")
        destination_button = AnimatedButton("Browse")
        destination_button.clicked.connect(self.select_destination_folder)

        grid.addWidget(source_label, 0, 0)
        grid.addWidget(self.source_edit, 0, 1)
        grid.addWidget(source_button, 0, 2)
        grid.addWidget(destination_label, 1, 0)
        grid.addWidget(self.destination_edit, 1, 1)
        grid.addWidget(destination_button, 1, 2)
        grid.setColumnStretch(1, 1)
        card.content_layout.addLayout(grid)
        return card

    def _build_best_photo_card(self) -> QWidget:
        card = GlassCard(
            "Photographer Culling AI",
            "Choose a source folder, then Nova ranks every frame into final SELECT and REJECT decisions with photographer-style culling.",
        )

        action_row = QHBoxLayout()
        action_row.setSpacing(14)

        self.best_photo_button = AnimatedButton("Start Culling AI", accent=True)
        self.best_photo_button.clicked.connect(self.start_photo_selection)

        hint = QLabel("Results open in a two-column final selection page. Manual changes can be saved so Nova learns this client style.")
        hint.setObjectName("InlineHint")
        hint.setWordWrap(True)

        action_row.addWidget(hint, 1)
        action_row.addWidget(self.best_photo_button, 0, Qt.AlignmentFlag.AlignRight)
        card.content_layout.addLayout(action_row)
        return card

    def _build_query_card(self) -> QWidget:
        card = GlassCard(
            "2. Query Input + OCR",
            "Type image names, paste keywords, or pull text directly from a screenshot. Matching ignores extensions and handles typos intelligently.",
        )

        self.query_input = QPlainTextEdit()
        self.query_input.setPlaceholderText(
            "Type image names or keywords here.\nUse commas or new lines.\nExample:\nhero-banner\nproduct shot 02\npackaging_final"
        )
        self.query_input.setMinimumHeight(210)

        button_row = QHBoxLayout()
        self.ocr_button = AnimatedButton("Import Screenshot For OCR")
        self.ocr_button.clicked.connect(self.select_screenshot_for_ocr)
        clear_button = AnimatedButton("Clear Text")
        clear_button.clicked.connect(self.query_input.clear)
        button_row.addWidget(self.ocr_button)
        button_row.addWidget(clear_button)
        button_row.addStretch(1)

        hint = QLabel("OCR cleans screenshot text automatically before it reaches the matching engine.")
        hint.setObjectName("InlineHint")
        hint.setWordWrap(True)

        card.content_layout.addWidget(self.query_input)
        card.content_layout.addLayout(button_row)
        card.content_layout.addWidget(hint)
        return card

    def _build_reference_card(self) -> QWidget:
        card = GlassCard(
            "3. Visual Reference Images",
            "Drop example images here to search by visual similarity. The app will compare their embeddings against the source library.",
        )

        self.reference_list = ReferenceListWidget()
        self.reference_list.setMinimumHeight(190)

        controls = QHBoxLayout()
        add_button = AnimatedButton("Add Images")
        add_button.clicked.connect(self.add_reference_images)
        remove_button = AnimatedButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_reference_images)
        clear_button = AnimatedButton("Clear All")
        clear_button.clicked.connect(self.reference_list.clear)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)
        controls.addWidget(clear_button)
        controls.addStretch(1)

        hint = QLabel("Supported: JPG, JPEG, PNG, WEBP. Drag files straight into the list.")
        hint.setObjectName("InlineHint")
        hint.setWordWrap(True)

        card.content_layout.addWidget(self.reference_list)
        card.content_layout.addLayout(controls)
        card.content_layout.addWidget(hint)
        return card

    def _build_options_card(self) -> QWidget:
        card = GlassCard(
            "4. Matching Controls",
            "Tune fuzzy name sensitivity and visual strictness. AI keeps one strongest unique image per reference.",
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)

        fuzzy_label = QLabel("Fuzzy Name Threshold")
        self.fuzzy_spin = QSpinBox()
        self.fuzzy_spin.setRange(60, 98)
        self.fuzzy_spin.setValue(82)
        self.fuzzy_spin.setSuffix("%")

        visual_label = QLabel("Visual Similarity Threshold")
        self.visual_spin = QDoubleSpinBox()
        self.visual_spin.setRange(0.40, 0.99)
        self.visual_spin.setSingleStep(0.01)
        self.visual_spin.setDecimals(2)
        self.visual_spin.setValue(0.78)

        candidate_label = QLabel("AI Candidate Depth")
        self.visual_candidate_depth_spin = QSpinBox()
        self.visual_candidate_depth_spin.setRange(2, 24)
        self.visual_candidate_depth_spin.setValue(8)

        fuzzy_hint = QLabel("Lower values find more typo variants but may increase false positives.")
        fuzzy_hint.setObjectName("InlineHint")
        visual_hint = QLabel("Raise this when you only want very close visual matches.")
        visual_hint.setObjectName("InlineHint")
        candidate_hint = QLabel(
            "Only one unique best image is copied per reference. Higher depth gives the AI more fallback choices when similar matches overlap."
        )
        candidate_hint.setObjectName("InlineHint")
        candidate_hint.setWordWrap(True)

        grid.addWidget(fuzzy_label, 0, 0)
        grid.addWidget(self.fuzzy_spin, 0, 1)
        grid.addWidget(visual_label, 1, 0)
        grid.addWidget(self.visual_spin, 1, 1)
        grid.addWidget(candidate_label, 2, 0)
        grid.addWidget(self.visual_candidate_depth_spin, 2, 1)
        grid.addWidget(fuzzy_hint, 3, 0, 1, 2)
        grid.addWidget(visual_hint, 4, 0, 1, 2)
        grid.addWidget(candidate_hint, 5, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        card.content_layout.addLayout(grid)
        return card

    def _build_actions_card(self) -> QWidget:
        card = GlassCard("5. Run + Guidance", "Start the full pipeline, export the final report, or review the built-in usage guide.")

        action_row = QHBoxLayout()
        action_row.setSpacing(14)

        help_button = AnimatedButton("Open Help")
        help_button.clicked.connect(self.show_help_dialog)

        self.export_button = AnimatedButton("Export Report")
        self.export_button.clicked.connect(self.export_report)
        self.export_button.setEnabled(False)

        self.open_destination_button = AnimatedButton("Open Destination")
        self.open_destination_button.clicked.connect(self.open_destination_folder)
        self.open_destination_button.setEnabled(False)

        self.start_button = AnimatedButton("Start Smart Match", accent=True)
        self.start_button.clicked.connect(self.start_processing)

        action_row.addWidget(help_button)
        action_row.addWidget(self.export_button)
        action_row.addWidget(self.open_destination_button)
        action_row.addStretch(1)
        action_row.addWidget(self.start_button)
        card.content_layout.addLayout(action_row)
        return card

    def _build_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(18)

        activity_card = GlassCard("Live Activity", "Real-time scanning, matching, copy progress, and visual engine status.")

        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.spinner = SpinnerWidget()
        self.spinner.hide()
        self.status_label = QLabel("Ready to scan.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(self.status_label, 1)

        self.engine_label = QLabel("Vision engine: Awaiting job")
        self.engine_label.setObjectName("EngineLabel")
        self.engine_label.setWordWrap(True)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()

        self.progress_bar = SmoothProgressBar()
        self.progress_bar.setFixedHeight(18)

        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(12)
        stats_layout.setVerticalSpacing(12)
        self.total_tile = StatTile("Total Images", "0")
        self.copied_tile = StatTile("Copied Images", "0")
        self.remaining_tile = StatTile("Remaining Images", "0")
        stats_layout.addWidget(self.total_tile, 0, 0)
        stats_layout.addWidget(self.copied_tile, 0, 1)
        stats_layout.addWidget(self.remaining_tile, 0, 2)

        activity_card.content_layout.addLayout(status_row)
        activity_card.content_layout.addWidget(self.engine_label)
        activity_card.content_layout.addWidget(self.warning_label)
        activity_card.content_layout.addWidget(self.progress_bar)
        activity_card.content_layout.addLayout(stats_layout)

        result_card = GlassCard(
            "Final Result Report",
            "Review copied files, missing items, reference images without confident matches, and the active vision backend.",
        )
        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(False)
        self.result_browser.setPlaceholderText("Run a matching job to see the final report here.")
        result_card.content_layout.addWidget(self.result_browser)

        layout.addWidget(activity_card)
        layout.addWidget(result_card, 1)
        return container

    def _apply_theme(self) -> None:
        apply_app_theme()
        self.setStyleSheet(build_stylesheet())

    def _create_avatar_label(self, size: int) -> QLabel:
        label = QLabel()
        label.setObjectName("AvatarLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(size, size)
        return label

    def set_authenticated_user(self, user: AuthUser) -> None:
        friendly_name = user.friendly_name or "Authenticated User"

        self._current_user_name = friendly_name
        self._current_user_email = user.email or friendly_name
        self.user_name_label.setText(friendly_name)
        self.user_email_label.setText(user.email or "Email unavailable")
        self.user_provider_label.setText("Provider: Google Sign-In")

        self.user_avatar_label.setPixmap(self._build_avatar_pixmap(None, self._current_user_name, 58))
        if user.photo_url:
            self.avatar_network.get(QNetworkRequest(QUrl(user.photo_url)))

    def _on_avatar_reply(self, reply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(bytes(reply.readAll())):
                self.user_avatar_label.setPixmap(self._build_avatar_pixmap(pixmap, self._current_user_name, 58))
        finally:
            reply.deleteLater()

    def _build_avatar_pixmap(self, source: QPixmap | None, name: str, size: int) -> QPixmap:
        avatar = QPixmap(size, size)
        avatar.fill(Qt.GlobalColor.transparent)

        painter = QPainter(avatar)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        if source is not None and not source.isNull():
            scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x_offset = max(0, int((scaled.width() - size) / 2))
            y_offset = max(0, int((scaled.height() - size) / 2))
            painter.drawPixmap(0, 0, scaled, x_offset, y_offset, size, size)
        else:
            gradient = QLinearGradient(0, 0, size, size)
            gradient.setColorAt(0.0, QColor("#4e84ff"))
            gradient.setColorAt(1.0, QColor("#36d7ff"))
            painter.fillPath(path, gradient)

            initials = self._initials_from_name(name)
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(size * 0.28)))
            painter.setFont(font)
            painter.drawText(avatar.rect(), Qt.AlignmentFlag.AlignCenter, initials)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        painter.drawEllipse(0, 0, size - 1, size - 1)
        painter.end()
        return avatar

    @staticmethod
    def _initials_from_name(name: str) -> str:
        parts = [part for part in name.replace("_", " ").split() if part]
        if not parts:
            return "N"
        if len(parts) == 1:
            return parts[0][:1].upper()
        return (parts[0][:1] + parts[1][:1]).upper()

    def _set_stat_titles(self, second_title: str, third_title: str) -> None:
        self.total_tile.set_title("Total Images")
        self.copied_tile.set_title(second_title)
        self.remaining_tile.set_title(third_title)

    def _photo_profile_id(self) -> str:
        return (self._current_user_email or self._current_user_name or "local-photographer").strip()

    def select_source_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_edit.setText(folder)

    def select_destination_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.destination_edit.setText(folder)

    def select_screenshot_for_ocr(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Screenshot For OCR",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not file_path:
            return

        self.ocr_button.setEnabled(False)
        self.spinner.start()
        self.status_label.setText("Reading screenshot and extracting text with OCR...")
        self.ocr_thread = OCRThread(file_path)
        self.ocr_thread.finished_with_queries.connect(self.on_ocr_complete)
        self.ocr_thread.error_occurred.connect(self.on_ocr_error)
        self.ocr_thread.finished.connect(lambda: self.ocr_button.setEnabled(True))
        self.ocr_thread.finished.connect(lambda: self.spinner.stop() if self.worker is None else None)
        self.ocr_thread.start()

    def on_ocr_complete(self, queries: list[str]) -> None:
        existing_queries = parse_queries(self.query_input.toPlainText())
        seen = {item.casefold() for item in existing_queries}
        new_items = [item for item in queries if item.casefold() not in seen]
        merged = existing_queries + new_items
        self.query_input.setPlainText("\n".join(merged))

        if new_items:
            self.status_label.setText(f"OCR complete. Added {len(new_items)} cleaned query item(s).")
        else:
            self.status_label.setText("OCR complete, but no new clean query terms were found.")

    def on_ocr_error(self, message: str) -> None:
        self.status_label.setText("OCR failed.")
        QMessageBox.warning(self, "OCR Error", message)

    def add_reference_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Reference Images",
            "",
            "Images (*.jpg *.jpeg *.png *.webp)",
        )
        if files:
            self.reference_list.add_files(files)

    def remove_selected_reference_images(self) -> None:
        for item in self.reference_list.selectedItems():
            row = self.reference_list.row(item)
            self.reference_list.takeItem(row)

    def show_help_dialog(self) -> None:
        HelpDialog(self).exec()

    def open_destination_folder(self) -> None:
        destination = self.destination_edit.text().strip()
        if destination and os.path.isdir(destination):
            QDesktopServices.openUrl(QUrl.fromLocalFile(destination))

    def start_photo_selection(self) -> None:
        source_dir = self.source_edit.text().strip()
        if not source_dir:
            QMessageBox.warning(self, "Missing Source Folder", "Select a source folder before starting Culling AI.")
            return
        if not os.path.isdir(source_dir):
            QMessageBox.warning(self, "Invalid Source Folder", "The selected source folder is missing or invalid.")
            return
        if self.worker is not None or self.photo_worker is not None:
            QMessageBox.information(self, "Job In Progress", "Wait for the current scan to finish before starting another one.")
            return

        self.last_report_text = ""
        self.result_browser.clear()
        self.warning_label.hide()
        self.warning_label.clear()
        self.progress_bar.set_smooth_value(0)
        self.status_label.setText("Preparing photographer-grade culling scan...")
        self.engine_label.setText("Vision engine: Adaptive Culling AI")
        self._set_stat_titles("Selected Photos", "Rejected Photos")
        self.total_tile.set_value("0")
        self.copied_tile.set_value("0")
        self.remaining_tile.set_value("0")
        self.export_button.setEnabled(False)
        self.open_destination_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.best_photo_button.setEnabled(False)
        self.spinner.start()

        self.photo_worker = PhotoSelectionThread(source_dir, self._photo_profile_id())
        self.photo_worker.progress_changed.connect(self.progress_bar.set_smooth_value)
        self.photo_worker.status_changed.connect(self.status_label.setText)
        self.photo_worker.stats_changed.connect(self.update_photo_selection_stats)
        self.photo_worker.warning_emitted.connect(self.show_warning)
        self.photo_worker.engine_changed.connect(lambda name: self.engine_label.setText(f"Vision engine: {name}"))
        self.photo_worker.result_ready.connect(self.on_photo_selection_complete)
        self.photo_worker.error_occurred.connect(self.on_photo_selection_error)
        self.photo_worker.finished.connect(self.on_photo_worker_finished)
        self.photo_worker.start()

    def start_processing(self) -> None:
        source_dir = self.source_edit.text().strip()
        destination_dir = self.destination_edit.text().strip()
        queries = parse_queries(self.query_input.toPlainText())
        reference_images = self.reference_list.file_paths()

        if not source_dir:
            QMessageBox.warning(self, "Missing Source Folder", "Select a source folder before starting.")
            return
        if not destination_dir:
            QMessageBox.warning(self, "Missing Destination Folder", "Select a destination folder before starting.")
            return
        if not queries and not reference_images:
            QMessageBox.warning(
                self,
                "No Matching Input",
                "Add text queries, reference images, or both before starting the scan.",
            )
            return
        if self.worker is not None or self.photo_worker is not None:
            QMessageBox.information(self, "Job In Progress", "Wait for the current scan to finish before starting another one.")
            return

        is_valid, validation_message = validate_folder_pair(source_dir, destination_dir)
        if not is_valid:
            QMessageBox.warning(self, "Folder Validation", validation_message)
            return

        self.last_report_text = ""
        self.result_browser.clear()
        self.warning_label.hide()
        self.warning_label.clear()
        self.progress_bar.set_smooth_value(0)
        self.status_label.setText("Preparing scan...")
        self.engine_label.setText("Vision engine: Loading on demand")
        self._set_stat_titles("Copied Images", "Remaining Images")
        self.total_tile.set_value("0")
        self.copied_tile.set_value("0")
        self.remaining_tile.set_value("0")
        self.export_button.setEnabled(False)
        self.open_destination_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.best_photo_button.setEnabled(False)
        self.spinner.start()

        options = ProcessingOptions(
            fuzzy_threshold=self.fuzzy_spin.value(),
            visual_threshold=float(self.visual_spin.value()),
            visual_candidate_depth=self.visual_candidate_depth_spin.value(),
        )

        self.worker = ProcessingThread(source_dir, destination_dir, queries, reference_images, options)
        self.worker.progress_changed.connect(self.progress_bar.set_smooth_value)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.stats_changed.connect(self.update_stats)
        self.worker.warning_emitted.connect(self.show_warning)
        self.worker.engine_changed.connect(lambda name: self.engine_label.setText(f"Vision engine: {name}"))
        self.worker.result_ready.connect(self.on_processing_complete)
        self.worker.error_occurred.connect(self.on_processing_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def update_stats(self, total_images: int, copied_images: int, remaining_images: int) -> None:
        self.total_tile.set_value(str(total_images))
        self.copied_tile.set_value(str(copied_images))
        self.remaining_tile.set_value(str(remaining_images))

    def update_photo_selection_stats(self, total_images: int, selected_images: int, rejected_images: int) -> None:
        self.total_tile.set_value(str(total_images))
        self.copied_tile.set_value(str(selected_images))
        self.remaining_tile.set_value(str(rejected_images))

    def show_warning(self, warning_text: str) -> None:
        self.warning_label.setText(warning_text)
        self.warning_label.show()

    def on_processing_complete(self, result: MatchResult) -> None:
        self.last_report_text = result.report_text
        self.result_browser.setPlainText(result.report_text)
        self.export_button.setEnabled(True)
        self.open_destination_button.setEnabled(bool(result.copied_files))
        self.engine_label.setText(f"Vision engine: {result.vision_engine}")

        if result.copied_files:
            self.status_label.setText(f"Completed. Copied {len(result.copied_files)} image(s).")
        else:
            self.status_label.setText("Completed. No confident matches were copied.")

    def on_photo_selection_complete(self, result: PhotoSelectionResult) -> None:
        self.last_report_text = self._build_photo_selection_report(result)
        self.result_browser.setPlainText(self.last_report_text)
        self.engine_label.setText(f"Vision engine: {result.vision_engine}")
        self.export_button.setEnabled(True)
        self.open_destination_button.setEnabled(False)
        self.status_label.setText(
            f"Completed. Selected {len(result.selected_items)}, rejected {len(result.rejected_items)}."
        )

        self.photo_results_window = PhotoSelectionResultsWindow(result, self.destination_edit.text().strip())
        self.photo_results_window.show()
        self.photo_results_window.raise_()
        self.photo_results_window.activateWindow()

    def on_processing_error(self, traceback_text: str) -> None:
        self.last_report_text = traceback_text
        self.result_browser.setPlainText(traceback_text)
        self.status_label.setText("Processing failed.")
        QMessageBox.critical(
            self,
            "Processing Error",
            "The job could not complete. The traceback has been placed in the report panel for debugging.",
        )

    def on_photo_selection_error(self, traceback_text: str) -> None:
        self.last_report_text = traceback_text
        self.result_browser.setPlainText(traceback_text)
        self.status_label.setText("Culling AI scan failed.")
        QMessageBox.critical(
            self,
            "Culling AI Error",
            "The photo selection job could not complete. The traceback has been placed in the report panel for debugging.",
        )

    def on_worker_finished(self) -> None:
        self.spinner.stop()
        self.start_button.setEnabled(True)
        self.best_photo_button.setEnabled(True)
        self.worker = None

    def on_photo_worker_finished(self) -> None:
        self.spinner.stop()
        self.start_button.setEnabled(True)
        self.best_photo_button.setEnabled(True)
        self.photo_worker = None

    def _build_photo_selection_report(self, result: PhotoSelectionResult) -> str:
        lines = [
            "Photographer Culling AI Report",
            "==============================",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Summary",
            f"Source: {result.source_dir}",
            f"Total photos: {result.total_source_images}",
            f"Selected photos: {len(result.selected_items)}",
            f"Rejected photos: {len(result.rejected_items)}",
            f"Scan time: {result.elapsed_seconds:.2f}s",
            f"Vision engine: {result.vision_engine}",
            f"Shoot type: {result.shoot_type}",
            f"Learning profile: {result.profile_id}",
            f"Learning: {result.learning_summary}",
        ]

        if result.warnings:
            lines.extend(["", "Warnings"])
            lines.extend(f"- {warning}" for warning in result.warnings)

        if result.selected_items:
            lines.extend(["", "Selected Photos"])
            for item in result.selected_items[:150]:
                reason = item.reasons[0] if item.reasons else "Strong final pick"
                rank = item.metrics.get("relative_rank", "")
                cluster_id = item.metrics.get("cluster_id", "")
                lines.append(
                    f"- {Path(item.path).name}: Score: {item.score:.0f} | SELECT | "
                    f"rank {rank} | cluster {cluster_id} | {reason}"
                )
            if len(result.selected_items) > 150:
                lines.append(f"- ... {len(result.selected_items) - 150} additional selected photo(s)")

        if result.rejected_items:
            lines.extend(["", "Rejected Photos"])
            for item in result.rejected_items[:150]:
                reason = item.reasons[0] if item.reasons else "Strict reject after full evaluation"
                rank = item.metrics.get("relative_rank", "")
                cluster_id = item.metrics.get("cluster_id", "")
                lines.append(
                    f"- {Path(item.path).name}: Score: {item.score:.0f} | REJECT | "
                    f"rank {rank} | cluster {cluster_id} | {reason}"
                )
            if len(result.rejected_items) > 150:
                lines.append(f"- ... {len(result.rejected_items) - 150} additional rejected photo(s)")

        return "\n".join(lines)

    def export_report(self) -> None:
        if not self.last_report_text:
            QMessageBox.information(self, "No Report", "Run a scan before exporting a report.")
            return

        default_name = f"nova_image_scout_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report", default_name, "Text Files (*.txt)")
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(self.last_report_text)
        except OSError as exc:
            QMessageBox.warning(self, "Export Failed", f"Could not write the report:\n{exc}")
            return

        QMessageBox.information(self, "Report Exported", f"Report saved to:\n{file_path}")
