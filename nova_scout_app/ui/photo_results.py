from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from nova_scout_app.models import PhotoSelectionItem, PhotoSelectionResult
from nova_scout_app.services.file_ops import safe_copy_file, validate_folder_pair
from nova_scout_app.services.photo_selection import (
    REJECT_CATEGORY,
    SELECT_CATEGORY,
    record_culling_feedback,
)
from nova_scout_app.ui.widgets import AnimatedButton, BackdropWidget, GlassCard, PathDropLineEdit


class PhotoGridWidget(QListWidget):
    photo_double_clicked = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(158, 118))
        self.setGridSize(QSize(206, 176))
        self.setSpacing(8)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        photo_item = item.data(Qt.ItemDataRole.UserRole)
        if photo_item is not None:
            self.photo_double_clicked.emit(photo_item)

    def add_photo(self, photo_item: PhotoSelectionItem) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, photo_item)
        item.setIcon(_build_icon(photo_item.path))
        item.setText(_build_item_text(photo_item))
        item.setToolTip(_build_tooltip(photo_item))
        self.addItem(item)

    def remove_photo(self, photo_item: PhotoSelectionItem) -> None:
        for index in range(self.count()):
            item = self.item(index)
            current = item.data(Qt.ItemDataRole.UserRole)
            if current is not None and current.path == photo_item.path:
                self.takeItem(index)
                return


class PhotoSelectionResultsWindow(QMainWindow):
    def __init__(self, result: PhotoSelectionResult, destination_dir: str = "") -> None:
        super().__init__()
        self.result = result
        self.destination_dir = destination_dir
        self.setWindowTitle("Photographer Culling Results")
        self.setMinimumSize(1180, 780)
        self.resize(1380, 860)

        self.selected_list = PhotoGridWidget()
        self.rejected_list = PhotoGridWidget()
        self.selected_count_label = QLabel()
        self.rejected_count_label = QLabel()
        self.copy_status_label = QLabel("")
        self.feedback_status_label = QLabel("")

        self._setup_ui()
        self._load_items()
        self._refresh_counts()

    def _setup_ui(self) -> None:
        root = BackdropWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        header_card = GlassCard(
            "Photographer Culling Results",
            "Double-click thumbnails to flip them between SELECT and REJECT before saving client feedback.",
        )
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        summary = QLabel(
            f"Scanned {self.result.total_source_images} photo(s) in {self.result.elapsed_seconds:.2f}s. "
            f"Shoot: {self.result.shoot_type}. Engine: {self.result.vision_engine}"
        )
        summary.setObjectName("InlineHint")
        summary.setWordWrap(True)

        open_source_button = AnimatedButton("Open Source Folder")
        open_source_button.clicked.connect(self.open_source_folder)

        header_row.addWidget(summary, 1)
        header_row.addWidget(open_source_button, 0, Qt.AlignmentFlag.AlignRight)
        header_card.content_layout.addLayout(header_row)
        layout.addWidget(header_card)

        copy_card = GlassCard(
            "Copy SELECT Photos",
            "Send the final SELECT list into a destination folder after culling.",
        )
        copy_grid = QGridLayout()
        copy_grid.setHorizontalSpacing(14)
        copy_grid.setVerticalSpacing(12)

        destination_label = QLabel("Destination Folder")
        self.destination_edit = PathDropLineEdit(folder_only=True)
        self.destination_edit.setPlaceholderText("Drop or browse to the folder where selected photos should be copied")
        self.destination_edit.setText(self.destination_dir)

        browse_button = AnimatedButton("Browse")
        browse_button.clicked.connect(self.select_destination_folder)

        self.copy_selected_button = AnimatedButton("Copy Selected", accent=True)
        self.copy_selected_button.clicked.connect(self.copy_selected_photos)

        self.save_feedback_button = AnimatedButton("Save Feedback + Learn")
        self.save_feedback_button.clicked.connect(self.save_feedback)

        self.copy_status_label.setObjectName("InlineHint")
        self.copy_status_label.setWordWrap(True)
        self.feedback_status_label.setObjectName("InlineHint")
        self.feedback_status_label.setWordWrap(True)

        copy_grid.addWidget(destination_label, 0, 0)
        copy_grid.addWidget(self.destination_edit, 0, 1)
        copy_grid.addWidget(browse_button, 0, 2)
        copy_grid.addWidget(self.copy_selected_button, 0, 3)
        copy_grid.addWidget(self.save_feedback_button, 0, 4)
        copy_grid.addWidget(self.copy_status_label, 1, 1, 1, 4)
        copy_grid.addWidget(self.feedback_status_label, 2, 1, 1, 4)
        copy_grid.setColumnStretch(1, 1)
        copy_card.content_layout.addLayout(copy_grid)
        layout.addWidget(copy_card)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_column("SELECT", self.selected_count_label, self.selected_list))
        splitter.addWidget(self._build_column("REJECT", self.rejected_count_label, self.rejected_list))
        splitter.setSizes([690, 690])
        layout.addWidget(splitter, 1)

        self.selected_list.photo_double_clicked.connect(lambda item: self.move_photo(item, REJECT_CATEGORY))
        self.rejected_list.photo_double_clicked.connect(lambda item: self.move_photo(item, SELECT_CATEGORY))
        self.setCentralWidget(root)

    def _build_column(self, title: str, count_label: QLabel, photo_list: PhotoGridWidget) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ResultPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        count_label.setObjectName("PhotoCountLabel")
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        title_row.addWidget(count_label)

        layout.addLayout(title_row)
        layout.addWidget(photo_list, 1)
        return panel

    def _load_items(self) -> None:
        for item in self.result.selected_items:
            item.selected = True
            item.category = SELECT_CATEGORY
            self.selected_list.add_photo(item)
        for item in self.result.rejected_items:
            item.selected = False
            item.category = REJECT_CATEGORY
            self.rejected_list.add_photo(item)

    def _refresh_counts(self) -> None:
        self.selected_count_label.setText(str(self.selected_list.count()))
        self.rejected_count_label.setText(str(self.rejected_list.count()))

    def move_photo(self, photo_item: PhotoSelectionItem, target_category: str) -> None:
        self._remove_from_all_lists(photo_item)
        photo_item.category = target_category
        photo_item.selected = target_category == SELECT_CATEGORY
        photo_item.metrics["manual_override"] = target_category.lower()
        photo_item.metrics["final_category"] = target_category

        if target_category == SELECT_CATEGORY:
            photo_item.reasons = ["Human-approved select"]
            self.selected_list.add_photo(photo_item)
        else:
            photo_item.reasons = ["Human rejected after final review"]
            self.rejected_list.add_photo(photo_item)
        self._refresh_counts()

    def _remove_from_all_lists(self, photo_item: PhotoSelectionItem) -> None:
        self.selected_list.remove_photo(photo_item)
        self.rejected_list.remove_photo(photo_item)

    def open_source_folder(self) -> None:
        if os.path.isdir(self.result.source_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.result.source_dir))

    def select_destination_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.destination_edit.setText(folder)

    def selected_photo_paths(self) -> list[str]:
        paths: list[str] = []
        for index in range(self.selected_list.count()):
            item = self.selected_list.item(index)
            photo_item = item.data(Qt.ItemDataRole.UserRole)
            if photo_item is not None:
                paths.append(photo_item.path)
        return paths

    def all_photo_items(self) -> list[PhotoSelectionItem]:
        items: list[PhotoSelectionItem] = []
        for photo_list in (self.selected_list, self.rejected_list):
            for index in range(photo_list.count()):
                widget_item = photo_list.item(index)
                photo_item = widget_item.data(Qt.ItemDataRole.UserRole)
                if photo_item is not None:
                    items.append(photo_item)
        return items

    def save_feedback(self) -> None:
        try:
            summary = record_culling_feedback(
                profile_id=self.result.profile_id,
                shoot_type=self.result.shoot_type,
                items=self.all_photo_items(),
            )
        except OSError as exc:
            QMessageBox.warning(self, "Learning Failed", f"Could not save the learning profile:\n{exc}")
            return

        self.result.learning_summary = summary
        self.feedback_status_label.setText(summary)
        QMessageBox.information(self, "Learning Updated", summary)

    def copy_selected_photos(self) -> None:
        destination_dir = self.destination_edit.text().strip()
        selected_paths = self.selected_photo_paths()

        if not selected_paths:
            QMessageBox.information(self, "No Selected Photos", "Move at least one photo into Selected before copying.")
            return
        if not destination_dir:
            QMessageBox.warning(self, "Missing Destination Folder", "Choose a destination folder for the selected photos.")
            return

        is_valid, validation_message = validate_folder_pair(self.result.source_dir, destination_dir)
        if not is_valid:
            QMessageBox.warning(self, "Folder Validation", validation_message)
            return

        copied_paths: list[str] = []
        progress = QProgressDialog("Copying selected photos...", "Cancel", 0, len(selected_paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(250)

        try:
            for index, source_path in enumerate(selected_paths, start=1):
                if progress.wasCanceled():
                    break
                progress.setValue(index - 1)
                progress.setLabelText(f"Copying {Path(source_path).name}...")
                copied_paths.append(safe_copy_file(source_path, destination_dir))
        except OSError as exc:
            progress.close()
            QMessageBox.warning(self, "Copy Failed", f"Could not copy the selected photos:\n{exc}")
            return
        finally:
            progress.setValue(len(copied_paths))

        copied_count = len(copied_paths)
        self.copy_status_label.setText(f"Copied {copied_count} selected photo(s) to {destination_dir}")
        if copied_count:
            selected_path_set = set(selected_paths)
            for item in self.all_photo_items():
                if item.path in selected_path_set:
                    item.metrics["implicit_positive"] = "exported"
            try:
                summary = record_culling_feedback(
                    profile_id=self.result.profile_id,
                    shoot_type=self.result.shoot_type,
                    items=self.all_photo_items(),
                )
                self.result.learning_summary = summary
                self.feedback_status_label.setText(f"Export feedback saved. {summary}")
            except OSError:
                self.feedback_status_label.setText("Selected photos copied, but feedback learning could not be saved.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(destination_dir))
            QMessageBox.information(self, "Copy Complete", f"Copied {copied_count} selected photo(s).")


def _build_icon(path: str) -> QIcon:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid():
        size.scale(QSize(220, 170), Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(size)
    image = reader.read()

    if image.isNull():
        pixmap = QPixmap(158, 118)
        pixmap.fill(QColor("#182033"))
        return QIcon(pixmap)

    pixmap = QPixmap.fromImage(image)
    pixmap = pixmap.scaled(
        QSize(158, 118),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return QIcon(pixmap)


def _build_item_text(photo_item: PhotoSelectionItem) -> str:
    name = Path(photo_item.path).name
    reason = photo_item.reasons[0] if photo_item.reasons else "Rejected"
    return f"{name}\n{photo_item.category} | Score {photo_item.score:.0f} - {_short_reason(reason)}"


def _short_reason(reason: str) -> str:
    lowered = reason.casefold()
    if "duplicate" in lowered or "similar" in lowered:
        return "Similar alternate"
    if "overexposed" in lowered:
        return "Overexposed"
    if "underexposed" in lowered:
        return "Underexposed"
    if "blurry" in lowered:
        return "Too blurry"
    if "eyes" in lowered:
        return "Eyes closed"
    if "distraction" in lowered:
        return "Distracting"
    if "score" in lowered or "quality" in lowered:
        return "Low quality"
    if "creative" in lowered or "meaningful" in lowered:
        return "Creative / meaningful"
    if "human-approved" in lowered:
        return "Human select"
    return "Decision"


def _build_tooltip(photo_item: PhotoSelectionItem) -> str:
    lines = [
        Path(photo_item.path).name,
        photo_item.path,
        f"Score: {photo_item.score:.2f}",
        f"Category: {photo_item.category}",
        f"Relative rank: {photo_item.metrics.get('relative_rank', 'n/a')}",
        f"Cluster: {photo_item.metrics.get('cluster_id', 'n/a')}",
    ]
    if photo_item.reasons:
        lines.append("Reason:")
        lines.extend(f"- {reason}" for reason in photo_item.reasons)
    ai_category = photo_item.metrics.get("ai_category")
    if ai_category and ai_category != photo_item.category:
        lines.append(f"Original AI category: {ai_category}")
    return "\n".join(lines)
