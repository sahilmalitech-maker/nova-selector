from __future__ import annotations

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QProgressBar, QVBoxLayout, QWidget

from nova_scout_app.constants import APP_TITLE


class SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(860, 470)

        self._phase = 0.0
        self._progress = 10
        self._target_progress = 10
        self._value_index = 0
        self._value_fade_direction = "idle"
        self._value_messages = [
            "Select your best photos in seconds",
            "AI-powered smart photo selection",
            "Remove duplicates, blur, and weak frames faster",
            "Turn large shoots into clean selects with less manual work",
        ]

        self._timer = QTimer(self)
        self._timer.setInterval(18)
        self._timer.timeout.connect(self._tick)

        self._message_timer = QTimer(self)
        self._message_timer.setInterval(3400)
        self._message_timer.timeout.connect(self._rotate_value)

        self._build_ui()
        self._center_on_screen()

        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(320)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(56, 46, 56, 46)
        layout.setSpacing(10)

        self.eyebrow_label = QLabel(APP_TITLE)
        self.eyebrow_label.setObjectName("SplashEyebrow")

        self.title_label = QLabel("Select your best photos in seconds")
        self.title_label.setObjectName("SplashTitle")
        self.title_label.setWordWrap(True)

        self.subtitle_label = QLabel("AI-powered smart photo selection for fast review, cleaner culling, and sharper final picks.")
        self.subtitle_label.setObjectName("SplashSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.value_label = QLabel(self._value_messages[1])
        self.value_label.setObjectName("SplashValue")
        self.value_label.setWordWrap(True)
        self.value_label.setMinimumHeight(34)

        self.value_effect = QGraphicsOpacityEffect(self.value_label)
        self.value_label.setGraphicsEffect(self.value_effect)
        self.value_effect.setOpacity(1.0)
        self.value_fade = QPropertyAnimation(self.value_effect, b"opacity", self)
        self.value_fade.setDuration(520)
        self.value_fade.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.value_fade.finished.connect(self._on_value_fade_finished)

        self.status_label = QLabel("Starting Nova Scout")
        self.status_label.setObjectName("SplashStatus")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self._progress)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)

        self.tip_label = QLabel("Large libraries stay easier to review when AI clears the obvious misses first.")
        self.tip_label.setObjectName("SplashTip")
        self.tip_label.setWordWrap(True)

        layout.addStretch(2)
        layout.addWidget(self.eyebrow_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(6)
        layout.addWidget(self.value_label)
        layout.addSpacing(4)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.tip_label)
        layout.addStretch(1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()
        self._message_timer.start()

    def set_status(self, message: str, target_progress: int | None = None) -> None:
        self.status_label.setText(message)
        if target_progress is not None:
            self._target_progress = max(0, min(100, target_progress))

    def finish_and_close(self) -> None:
        self.fade.stop()
        self.fade.setStartValue(self.windowOpacity())
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.close)
        self.fade.start()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.028) % (math.pi * 2)
        if self._progress < self._target_progress:
            self._progress += 1
            self.progress_bar.setValue(self._progress)
        self.update()

    def _rotate_value(self) -> None:
        if self.value_fade.state() == QPropertyAnimation.State.Running:
            return
        self._value_fade_direction = "out"
        self.value_fade.setStartValue(self.value_effect.opacity())
        self.value_fade.setEndValue(0.0)
        self.value_fade.start()

    def _on_value_fade_finished(self) -> None:
        if self._value_fade_direction == "out":
            self._value_index = (self._value_index + 1) % len(self._value_messages)
            self.value_label.setText(self._value_messages[self._value_index])
            self._value_fade_direction = "in"
            self.value_fade.setStartValue(0.0)
            self.value_fade.setEndValue(1.0)
            self.value_fade.start()
        else:
            self._value_fade_direction = "idle"

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.center().x() - (self.width() // 2),
            geometry.center().y() - (self.height() // 2),
        )

    def _draw_tile(self, painter: QPainter, *, anchor_x: float, anchor_y: float, width: int, height: int, phase_offset: float, angle: float, selected: bool) -> None:
        center_x = self.width() * anchor_x + math.sin(self._phase + phase_offset) * 10
        center_y = self.height() * anchor_y + math.cos(self._phase * 0.9 + phase_offset) * 8
        rotation = angle + math.sin(self._phase * 0.6 + phase_offset) * 2

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(rotation)
        painter.setBrush(QColor(20, 27, 41, 190 if selected else 142))
        painter.setPen(QPen(QColor(100, 213, 255, 210) if selected else QColor(96, 116, 152, 110), 2 if selected else 1))
        painter.drawRoundedRect(int(-width / 2), int(-height / 2), width, height, 20, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(int(-width / 2 + 14), int(-height / 2 + 14), width - 28, 18, 9, 9)
        painter.drawRoundedRect(int(-width / 2 + 14), int(-height / 2 + 42), int(width * 0.35), height - 66, 12, 12)
        if selected:
            painter.setBrush(QColor(59, 195, 255, 220))
            painter.drawRoundedRect(int(width / 2 - 88), int(-height / 2 + 14), 74, 20, 10, 10)
            painter.setPen(QColor("#04101a"))
            painter.drawText(int(width / 2 - 78), int(-height / 2 + 29), "KEEP")
        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.setBrush(QColor(9, 15, 24, 238))
        painter.setPen(QColor(72, 96, 126, 72))
        painter.drawRoundedRect(rect, 30, 30)

        glows = [
            (QPointF(self.width() * 0.18, self.height() * 0.22), 190, QColor(58, 179, 255, 90)),
            (QPointF(self.width() * 0.84, self.height() * 0.24), 170, QColor(122, 90, 255, 78)),
            (QPointF(self.width() * 0.60, self.height() * 0.84), 230, QColor(22, 191, 166, 52)),
        ]
        for center, radius, color in glows:
            gradient = QRadialGradient(center, radius)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, radius, radius)

        ring_rect = self.rect().adjusted(48, 54, -48, -54)
        ring_rect.setWidth(96)
        ring_rect.setHeight(96)
        painter.setPen(QPen(QColor(103, 196, 255, 220), 5))
        painter.drawArc(ring_rect, int(self._phase * 160), 260 * 16)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(ring_rect, Qt.AlignmentFlag.AlignCenter, "N")

        painter.setPen(QPen(QColor(100, 144, 210, 32), 1))
        for index in range(3):
            y = self.height() * (0.34 + index * 0.16) + math.sin(self._phase + index) * 4
            painter.drawLine(360, int(y), self.width() - 42, int(y))

        self._draw_tile(painter, anchor_x=0.78, anchor_y=0.32, width=164, height=112, phase_offset=0.5, angle=-6, selected=True)
        self._draw_tile(painter, anchor_x=0.76, anchor_y=0.60, width=176, height=124, phase_offset=1.7, angle=5, selected=False)

        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.drawRoundedRect(rect, 30, 30)
