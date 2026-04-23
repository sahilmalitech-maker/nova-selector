from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)

from nova_scout_app.services.text_processing import is_image_file


class BackdropWidget(QWidget):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0f1117"))

        glows = [
            (QPointF(self.width() * 0.18, self.height() * 0.1), self.width() * 0.32, QColor(90, 120, 255, 85)),
            (QPointF(self.width() * 0.84, self.height() * 0.2), self.width() * 0.26, QColor(104, 58, 183, 72)),
            (QPointF(self.width() * 0.52, self.height() * 0.95), self.width() * 0.4, QColor(40, 192, 255, 45)),
        ]
        for center, radius, color in glows:
            gradient = QRadialGradient(center, radius)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, radius, radius)

        painter.fillRect(self.rect(), QColor(9, 12, 18, 65))
        super().paintEvent(event)


class GlassCard(QFrame):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("GlassCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 135))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("CardSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(14)
        layout.addLayout(self.content_layout)


class AnimatedButton(QPushButton):
    def __init__(self, text: str, accent: bool = False) -> None:
        super().__init__(text)
        self._scale = 1.0
        self.accent = accent
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)
        self.setObjectName("AccentButton" if accent else "SecondaryButton")

        self.scale_animation = QPropertyAnimation(self, b"scale", self)
        self.scale_animation.setDuration(140)
        self.scale_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(28 if accent else 18)
        self.shadow.setOffset(0, 10)
        self.shadow.setColor(QColor(52, 123, 255, 120 if accent else 65))
        self.setGraphicsEffect(self.shadow)

    @pyqtProperty(float)
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        self._scale = value
        self.update()

    def animate_scale(self, target: float) -> None:
        self.scale_animation.stop()
        self.scale_animation.setStartValue(self._scale)
        self.scale_animation.setEndValue(target)
        self.scale_animation.start()

    def enterEvent(self, event) -> None:
        self.animate_scale(1.02)
        self.shadow.setBlurRadius(36 if self.accent else 24)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.animate_scale(1.0)
        self.shadow.setBlurRadius(28 if self.accent else 18)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.animate_scale(0.97)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.animate_scale(1.02 if self.rect().contains(event.pos()) else 1.0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(self._scale, self._scale)
        painter.translate(-self.width() / 2, -self.height() / 2)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)


class SpinnerWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.setFixedSize(36, 36)

    def rotate(self) -> None:
        self.angle = (self.angle + 22) % 360
        self.update()

    def start(self) -> None:
        if not self.timer.isActive():
            self.timer.start(40)
        self.show()

    def stop(self) -> None:
        self.timer.stop()
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#57a1ff"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        rect = self.rect().adjusted(6, 6, -6, -6)
        rect.moveCenter(self.rect().center())
        painter.drawArc(rect, 30 * 16, 260 * 16)


class SmoothProgressBar(QProgressBar):
    def __init__(self) -> None:
        super().__init__()
        self.setRange(0, 100)
        self.setValue(0)
        self.animation = QPropertyAnimation(self, b"value", self)
        self.animation.setDuration(240)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_smooth_value(self, value: int) -> None:
        value = max(0, min(100, value))
        self.animation.stop()
        self.animation.setStartValue(self.value())
        self.animation.setEndValue(value)
        self.animation.start()


class PathDropLineEdit(QLineEdit):
    def __init__(self, folder_only: bool = True) -> None:
        super().__init__()
        self.folder_only = folder_only
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                local_file = url.toLocalFile()
                if not local_file:
                    continue
                if self.folder_only and os.path.isdir(local_file):
                    event.acceptProposedAction()
                    return
                if not self.folder_only and os.path.exists(local_file):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            local_file = url.toLocalFile()
            if not local_file:
                continue
            if self.folder_only and os.path.isdir(local_file):
                self.setText(local_file)
                event.acceptProposedAction()
                return
            if not self.folder_only and os.path.exists(local_file):
                self.setText(local_file)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class ReferenceListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(False)

    def file_paths(self) -> list[str]:
        return [self.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.count())]

    def add_files(self, file_paths: Sequence[str]) -> None:
        existing = set(self.file_paths())
        for file_path in file_paths:
            if not file_path or not os.path.isfile(file_path) or not is_image_file(file_path):
                continue
            if file_path in existing:
                continue
            item = QListWidgetItem(Path(file_path).name)
            item.setToolTip(file_path)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.addItem(item)
            existing.add(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_files(files)
        event.acceptProposedAction()


class StatTile(QFrame):
    def __init__(self, title: str, value: str = "0") -> None:
        super().__init__()
        self.setObjectName("StatTile")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.value_label.setWordWrap(False)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)
