from __future__ import annotations

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nova_scout_app.constants import APP_TITLE
from nova_scout_app.ui.widgets import AnimatedButton, SpinnerWidget


class AuthWindow(QMainWindow):
    google_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} Login")
        self.resize(1220, 820)
        self.setMinimumSize(980, 700)

        self._phase = 0.0
        self._feature_index = 0
        self._feature_fade_direction = "idle"
        self._feature_sets = [
            ("Stop spending hours selecting manually", "Massive shoots, duplicate bursts, and weak frames slow delivery down before real review even starts."),
            ("Nova AI isolates the strongest moments", "Blur, duplicates, and low-confidence frames fade away while the best shots rise to the surface."),
            ("Copy 5000 photos in minutes", "Move huge image sets faster while Nova Scout helps surface the strongest shots for delivery."),
            ("Turn raw chaos into a polished shortlist", "A cinematic review flow that brings speed, clarity, and confidence to every shoot."),
        ]

        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(16)
        self._motion_timer.timeout.connect(self._tick_background)

        self._feature_timer = QTimer(self)
        self._feature_timer.setInterval(4700)
        self._feature_timer.timeout.connect(self._rotate_feature)

        self._build_ui()
        self._motion_timer.start()
        self._feature_timer.start()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.addStretch(1)

        center_row = QHBoxLayout()
        center_row.addStretch(1)
        center_row.addWidget(self._build_center_card(), 0, Qt.AlignmentFlag.AlignCenter)
        center_row.addStretch(1)

        layout.addLayout(center_row)
        layout.addStretch(1)
        self.setCentralWidget(root)

    def _build_center_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("AuthCenterCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card.setMaximumWidth(710)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(38, 36, 38, 36)
        layout.setSpacing(18)

        brand = QLabel(APP_TITLE)
        brand.setObjectName("AuthBrand")

        title = QLabel("Select your best photos in seconds")
        title.setObjectName("AuthTitle")
        title.setWordWrap(True)

        subtitle = QLabel(
            "One-click Google access to a faster culling workspace built for large shoots, cleaner selects, "
            "and far less manual review."
        )
        subtitle.setObjectName("AuthSubtitle")
        subtitle.setWordWrap(True)

        rotating_panel = QWidget()
        rotating_panel.setMinimumHeight(96)
        rotating_layout = QVBoxLayout(rotating_panel)
        rotating_layout.setContentsMargins(0, 0, 0, 0)
        rotating_layout.setSpacing(6)

        self.feature_headline = QLabel(self._feature_sets[0][0])
        self.feature_headline.setObjectName("AuthValueHeadline")
        self.feature_headline.setWordWrap(True)

        self.feature_copy = QLabel(self._feature_sets[0][1])
        self.feature_copy.setObjectName("AuthSupportText")
        self.feature_copy.setWordWrap(True)

        rotating_layout.addWidget(self.feature_headline)
        rotating_layout.addWidget(self.feature_copy)

        self.feature_effect = QGraphicsOpacityEffect(rotating_panel)
        rotating_panel.setGraphicsEffect(self.feature_effect)
        self.feature_effect.setOpacity(1.0)
        self.feature_fade = QPropertyAnimation(self.feature_effect, b"opacity", self)
        self.feature_fade.setDuration(520)
        self.feature_fade.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.feature_fade.finished.connect(self._on_feature_fade_finished)

        metric_row = QHBoxLayout()
        metric_row.setSpacing(12)
        metric_row.addWidget(self._build_metric_pill("5000+", "photos culled faster"))
        metric_row.addWidget(self._build_metric_pill("AI", "better first-pass filtering"))
        metric_row.addWidget(self._build_metric_pill("Hours", "saved on manual review"))

        self.google_button = AnimatedButton("Continue with Google", accent=True)
        self.google_button.setMinimumHeight(58)
        self.google_button.clicked.connect(self.google_requested.emit)

        self.helper_label = QLabel("Google only. No typing. Your session stays ready for the next launch.")
        self.helper_label.setObjectName("AuthSupportText")
        self.helper_label.setWordWrap(True)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.spinner = SpinnerWidget()
        self.spinner.hide()
        self.status_label = QLabel("Continue with Google to open your culling workspace.")
        self.status_label.setObjectName("AuthStatus")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(self.status_label, 1)

        layout.addWidget(brand)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(rotating_panel)
        layout.addLayout(metric_row)
        layout.addSpacing(6)
        layout.addWidget(self.google_button)
        layout.addWidget(self.helper_label)
        layout.addLayout(status_row)
        return card

    def _build_metric_pill(self, value: str, label: str) -> QWidget:
        pill = QFrame()
        pill.setObjectName("MetricPill")
        layout = QVBoxLayout(pill)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        copy_label = QLabel(label)
        copy_label.setObjectName("MetricLabel")
        copy_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(copy_label)
        return pill

    def _tick_background(self) -> None:
        self._phase += 0.013
        self.update()

    def _rotate_feature(self) -> None:
        if self.feature_fade.state() == QPropertyAnimation.State.Running:
            return
        self._feature_fade_direction = "out"
        self.feature_fade.setStartValue(self.feature_effect.opacity())
        self.feature_fade.setEndValue(0.0)
        self.feature_fade.start()

    def _on_feature_fade_finished(self) -> None:
        if self._feature_fade_direction == "out":
            self._feature_index = (self._feature_index + 1) % len(self._feature_sets)
            headline, copy = self._feature_sets[self._feature_index]
            self.feature_headline.setText(headline)
            self.feature_copy.setText(copy)
            self._feature_fade_direction = "in"
            self.feature_fade.setStartValue(0.0)
            self.feature_fade.setEndValue(1.0)
            self.feature_fade.start()
        else:
            self._feature_fade_direction = "idle"

    def set_busy(self, busy: bool, message: str) -> None:
        self.google_button.setEnabled(not busy)
        self.reset_status(message)
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()

    def set_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setObjectName("AuthStatusError")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.spinner.stop()

    def set_success(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setObjectName("AuthStatusSuccess")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.spinner.stop()

    def reset_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setObjectName("AuthStatus")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _draw_floating_frame(
        self,
        painter: QPainter,
        *,
        anchor_x: float,
        anchor_y: float,
        width: int,
        height: int,
        phase_offset: float,
        base_angle: float,
        selected: bool,
        variant: str,
    ) -> None:
        margin_x = width * 0.65
        margin_y = height * 0.75
        available_width = max(1.0, self.width() - margin_x * 2)
        available_height = max(1.0, self.height() - margin_y * 2)

        drift_x = (
            math.sin(self._phase * 0.31 + phase_offset) * 10
            + math.cos(self._phase * 0.11 + phase_offset * 1.9) * 6
        )
        drift_y = (
            math.cos(self._phase * 0.23 + phase_offset * 1.1) * 8
            + math.sin(self._phase * 0.09 + phase_offset * 2.3) * 5
        )
        center_x = margin_x + available_width * anchor_x + drift_x
        center_y = margin_y + available_height * anchor_y + drift_y
        rotation = (
            base_angle
            + math.sin(self._phase * 0.17 + phase_offset) * 1.6
            + math.cos(self._phase * 0.07 + phase_offset * 1.3) * 0.9
        )

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(rotation)

        border = QColor(107, 210, 255, 212) if selected else QColor(91, 116, 156, 118)
        fill = QColor(20, 27, 41, 202 if selected else 144)
        painter.setBrush(fill)
        painter.setPen(QPen(border, 2 if selected else 1))
        painter.drawRoundedRect(int(-width / 2), int(-height / 2), width, height, 20, 20)

        self._paint_card_content(
            painter,
            width=width,
            height=height,
            phase_offset=phase_offset,
            selected=selected,
            variant=variant,
        )

        painter.restore()

    def _paint_card_content(
        self,
        painter: QPainter,
        *,
        width: int,
        height: int,
        phase_offset: float,
        selected: bool,
        variant: str,
    ) -> None:
        header_rect = QRectF(-width / 2 + 14, -height / 2 + 14, width - 28, 16)
        preview_rect = QRectF(-width / 2 + 14, -height / 2 + 38, width * 0.42, height - 62)
        right_column_x = preview_rect.right() + 10
        right_column_width = width / 2 - 18

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 16))
        painter.drawRoundedRect(header_rect, 8, 8)

        for idx in range(3):
            dot_x = header_rect.left() + 10 + idx * 12
            dot_color = QColor(71, 208, 255, 210) if idx == int(abs(math.sin(self._phase * 0.8 + phase_offset)) * 2.8) else QColor(255, 255, 255, 48)
            painter.setBrush(dot_color)
            painter.drawEllipse(QRectF(dot_x, header_rect.top() + 4, 6, 6))

        preview_gradient = QLinearGradient(preview_rect.left(), preview_rect.top(), preview_rect.right(), preview_rect.bottom())
        if selected:
            preview_gradient.setColorAt(0.0, QColor(52, 126, 255, 150))
            preview_gradient.setColorAt(1.0, QColor(40, 201, 255, 82))
        else:
            preview_gradient.setColorAt(0.0, QColor(78, 92, 126, 120))
            preview_gradient.setColorAt(1.0, QColor(34, 48, 72, 92))
        painter.setBrush(preview_gradient)
        painter.drawRoundedRect(preview_rect, 14, 14)

        shimmer_center = preview_rect.left() + (preview_rect.width() + 42) * ((math.sin(self._phase * 0.42 + phase_offset) + 1.0) / 2.0) - 21
        shimmer = QLinearGradient(shimmer_center - 20, preview_rect.top(), shimmer_center + 20, preview_rect.bottom())
        shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
        shimmer.setColorAt(0.5, QColor(255, 255, 255, 34 if selected else 20))
        shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(shimmer)
        painter.drawRoundedRect(preview_rect, 14, 14)

        if variant == "raw":
            self._paint_raw_preview(painter, preview_rect, phase_offset)
        elif variant == "compare":
            self._paint_compare_preview(painter, preview_rect, phase_offset)
        elif variant == "analyze":
            self._paint_analysis_preview(painter, preview_rect, phase_offset)
        else:
            self._paint_selected_preview(painter, preview_rect, phase_offset)

        painter.setPen(Qt.PenStyle.NoPen)
        for idx in range(3):
            bar_width_factor = 0.34 + 0.52 * ((math.sin(self._phase * (0.44 + idx * 0.08) + phase_offset + idx) + 1.0) / 2.0)
            bar_rect = QRectF(
                right_column_x,
                -height / 2 + 42 + idx * 18,
                right_column_width,
                10,
            )
            painter.setBrush(QColor(255, 255, 255, 10))
            painter.drawRoundedRect(bar_rect, 5, 5)

            fill_rect = QRectF(bar_rect.left(), bar_rect.top(), bar_rect.width() * bar_width_factor, bar_rect.height())
            fill_gradient = QLinearGradient(fill_rect.left(), fill_rect.top(), fill_rect.right(), fill_rect.bottom())
            fill_gradient.setColorAt(0.0, QColor(77, 132, 255, 170 if selected else 110))
            fill_gradient.setColorAt(1.0, QColor(78, 224, 255, 190 if selected else 120))
            painter.setBrush(fill_gradient)
            painter.drawRoundedRect(fill_rect, 5, 5)

        if variant == "analyze":
            for idx in range(3):
                focus_x = right_column_x + right_column_width * (0.18 + idx * 0.24)
                focus_y = -height / 2 + 48 + idx * 16
                pulse = 3 + ((math.sin(self._phase * 0.52 + phase_offset + idx) + 1.0) / 2.0) * 3
                painter.setBrush(QColor(85, 220, 255, 185))
                painter.drawEllipse(QRectF(focus_x, focus_y, pulse, pulse))
        elif variant == "selected":
            hero_strip = QRectF(right_column_x, -height / 2 + 42, right_column_width * 0.92, 28)
            hero_gradient = QLinearGradient(hero_strip.left(), hero_strip.top(), hero_strip.right(), hero_strip.bottom())
            hero_gradient.setColorAt(0.0, QColor(82, 160, 255, 135))
            hero_gradient.setColorAt(1.0, QColor(72, 232, 255, 165))
            painter.setBrush(hero_gradient)
            painter.drawRoundedRect(hero_strip, 9, 9)

        thumb_y = height / 2 - 24
        for idx in range(3):
            thumb_rect = QRectF(-width / 2 + 14 + idx * 28, thumb_y, 20, 14)
            alpha = 22 + int(((math.cos(self._phase * 0.48 + phase_offset + idx * 0.6) + 1.0) / 2.0) * 22)
            painter.setBrush(QColor(255, 255, 255, alpha))
            painter.drawRoundedRect(thumb_rect, 7, 7)

        score_pulse = 0.45 + 0.25 * ((math.sin(self._phase * 0.37 + phase_offset) + 1.0) / 2.0)
        footer_rect = QRectF(right_column_x, height / 2 - 24, right_column_width * score_pulse, 14)
        footer_gradient = QLinearGradient(footer_rect.left(), footer_rect.top(), footer_rect.right(), footer_rect.bottom())
        footer_gradient.setColorAt(0.0, QColor(255, 255, 255, 12))
        footer_gradient.setColorAt(1.0, QColor(255, 255, 255, 26 if selected else 16))
        painter.setBrush(footer_gradient)
        painter.drawRoundedRect(footer_rect, 7, 7)

        accent_alpha = 110 if variant == "selected" else 56
        accent = QRectF(width / 2 - 30, -height / 2 + 16, 9, 9)
        painter.setBrush(QColor(89, 241, 212, accent_alpha))
        painter.drawEllipse(accent)
        painter.setBrush(QColor(89, 241, 212, 24 if variant == "selected" else 14))
        painter.drawEllipse(QRectF(accent.left() - 5, accent.top() - 5, 19, 19))

    def _paint_raw_preview(self, painter: QPainter, preview_rect: QRectF, phase_offset: float) -> None:
        for row in range(2):
            for col in range(2):
                cell = QRectF(
                    preview_rect.left() + 8 + col * (preview_rect.width() * 0.44),
                    preview_rect.top() + 8 + row * (preview_rect.height() * 0.42),
                    preview_rect.width() * 0.38,
                    preview_rect.height() * 0.30,
                )
                pulse = 8 + math.sin(self._phase * 0.34 + phase_offset + row + col) * 3
                painter.setBrush(QColor(255, 255, 255, 14 + int((row + col) * 3)))
                painter.drawRoundedRect(cell, 10, 10)
                painter.setBrush(QColor(255, 255, 255, 10))
                painter.drawRoundedRect(QRectF(cell.left() + 6, cell.top() + pulse, cell.width() * 0.72, 8), 4, 4)

    def _paint_compare_preview(self, painter: QPainter, preview_rect: QRectF, phase_offset: float) -> None:
        left = QRectF(preview_rect.left() + 8, preview_rect.top() + 10, preview_rect.width() * 0.42, preview_rect.height() - 20)
        right = QRectF(preview_rect.left() + preview_rect.width() * 0.50, preview_rect.top() + 10, preview_rect.width() * 0.32, preview_rect.height() - 20)
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.drawRoundedRect(left, 10, 10)
        painter.drawRoundedRect(right, 10, 10)
        divider_x = preview_rect.left() + preview_rect.width() * (0.38 + 0.08 * ((math.sin(self._phase * 0.36 + phase_offset) + 1.0) / 2.0))
        painter.setPen(QPen(QColor(110, 228, 255, 120), 2))
        painter.drawLine(int(divider_x), int(preview_rect.top() + 8), int(divider_x), int(preview_rect.bottom() - 8))
        painter.setBrush(QColor(110, 228, 255, 180))
        painter.drawEllipse(QRectF(divider_x - 4, preview_rect.center().y() - 4, 8, 8))

    def _paint_analysis_preview(self, painter: QPainter, preview_rect: QRectF, phase_offset: float) -> None:
        blob_one = QRectF(
            preview_rect.left() + 10 + math.sin(self._phase * 0.28 + phase_offset) * 3,
            preview_rect.top() + 11,
            preview_rect.width() * 0.56,
            preview_rect.height() * 0.42,
        )
        blob_two = QRectF(
            preview_rect.left() + preview_rect.width() * 0.22,
            preview_rect.top() + preview_rect.height() * 0.42 + math.cos(self._phase * 0.34 + phase_offset) * 2,
            preview_rect.width() * 0.52,
            preview_rect.height() * 0.30,
        )
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawRoundedRect(blob_one, 10, 10)
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.drawRoundedRect(blob_two, 10, 10)
        scan_y = preview_rect.top() + preview_rect.height() * ((math.sin(self._phase * 0.56 + phase_offset) + 1.0) / 2.0)
        painter.setPen(QPen(QColor(137, 229, 255, 80), 1))
        painter.drawLine(int(preview_rect.left() + 8), int(scan_y), int(preview_rect.right() - 8), int(scan_y))

    def _paint_selected_preview(self, painter: QPainter, preview_rect: QRectF, phase_offset: float) -> None:
        hero = QRectF(preview_rect.left() + 10, preview_rect.top() + 10, preview_rect.width() - 20, preview_rect.height() * 0.58)
        hero_gradient = QLinearGradient(hero.left(), hero.top(), hero.right(), hero.bottom())
        hero_gradient.setColorAt(0.0, QColor(83, 147, 255, 150))
        hero_gradient.setColorAt(1.0, QColor(58, 226, 255, 90))
        painter.setBrush(hero_gradient)
        painter.drawRoundedRect(hero, 12, 12)
        sparkle_x = hero.left() + hero.width() * ((math.sin(self._phase * 0.42 + phase_offset) + 1.0) / 2.0)
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawEllipse(QRectF(sparkle_x - 7, hero.top() + hero.height() * 0.24, 14, 14))
        for idx in range(3):
            chip = QRectF(preview_rect.left() + 10 + idx * 26, preview_rect.bottom() - 24, 18, 12)
            painter.setBrush(QColor(255, 255, 255, 20 + idx * 8))
            painter.drawRoundedRect(chip, 6, 6)

    @staticmethod
    def _cubic_point(p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF, t: float) -> QPointF:
        inv = 1.0 - t
        x = (
            inv * inv * inv * p0.x()
            + 3 * inv * inv * t * p1.x()
            + 3 * inv * t * t * p2.x()
            + t * t * t * p3.x()
        )
        y = (
            inv * inv * inv * p0.y()
            + 3 * inv * inv * t * p1.y()
            + 3 * inv * t * t * p2.y()
            + t * t * t * p3.y()
        )
        return QPointF(x, y)

    def _draw_story_stream(
        self,
        painter: QPainter,
        *,
        start: QPointF,
        control_one: QPointF,
        control_two: QPointF,
        end: QPointF,
        base_color: QColor,
        width: float,
        speed: float,
        particle_count: int,
    ) -> None:
        path = QPainterPath(start)
        path.cubicTo(control_one, control_two, end)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(base_color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

        for index in range(particle_count):
            t = (self._phase * speed + index / particle_count) % 1.0
            point = self._cubic_point(start, control_one, control_two, end, t)
            radius = 2.0 + 2.4 * ((math.sin(self._phase * 0.7 + index) + 1.0) / 2.0)
            glow = QColor(base_color.red(), base_color.green(), base_color.blue(), 32)
            particle = QColor(base_color.red(), base_color.green(), base_color.blue(), 170)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(point, radius * 2.2, radius * 2.2)
            painter.setBrush(particle)
            painter.drawEllipse(point, radius, radius)

    def _draw_storytelling_background(self, painter: QPainter) -> None:
        left_entry = QPointF(self.width() * 0.10, self.height() * 0.49)
        center_hub = QPointF(self.width() * 0.44, self.height() * 0.47)
        top_exit = QPointF(self.width() * 0.83, self.height() * 0.28)
        bottom_exit = QPointF(self.width() * 0.84, self.height() * 0.73)

        self._draw_problem_zone(painter)
        self._draw_solution_zone(painter, center_hub)
        self._draw_output_zone(painter)

        self._draw_story_stream(
            painter,
            start=left_entry,
            control_one=QPointF(self.width() * 0.22, self.height() * 0.28),
            control_two=QPointF(self.width() * 0.30, self.height() * 0.56),
            end=center_hub,
            base_color=QColor(88, 123, 176, 38),
            width=2.0,
            speed=0.055,
            particle_count=7,
        )
        self._draw_story_stream(
            painter,
            start=center_hub,
            control_one=QPointF(self.width() * 0.54, self.height() * 0.36),
            control_two=QPointF(self.width() * 0.68, self.height() * 0.22),
            end=top_exit,
            base_color=QColor(63, 197, 255, 42),
            width=2.4,
            speed=0.082,
            particle_count=8,
        )
        self._draw_story_stream(
            painter,
            start=center_hub,
            control_one=QPointF(self.width() * 0.56, self.height() * 0.62),
            control_two=QPointF(self.width() * 0.68, self.height() * 0.82),
            end=bottom_exit,
            base_color=QColor(74, 227, 196, 36),
            width=2.2,
            speed=0.071,
            particle_count=8,
        )

        for index in range(11):
            seed = index * 0.55
            x = self.width() * 0.05 + self.width() * 0.18 * ((math.sin(self._phase * 0.17 + seed) + 1.0) / 2.0)
            y = self.height() * (0.24 + 0.052 * index) + math.cos(self._phase * 0.21 + seed) * 8
            size = 4 + ((math.sin(self._phase * 0.33 + seed) + 1.0) / 2.0) * 4
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(118, 142, 186, 54))
            painter.drawEllipse(QPointF(x, y), size, size)

        hub_outer = 40 + math.sin(self._phase * 0.24) * 3
        hub_inner = 17 + math.cos(self._phase * 0.32) * 2
        hub_gradient = QRadialGradient(center_hub, hub_outer)
        hub_gradient.setColorAt(0.0, QColor(78, 199, 255, 52))
        hub_gradient.setColorAt(1.0, QColor(78, 199, 255, 0))
        painter.setBrush(hub_gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_hub, hub_outer, hub_outer)
        painter.setPen(QPen(QColor(90, 221, 255, 70), 1.5))
        painter.drawEllipse(center_hub, hub_inner, hub_inner)
        painter.drawEllipse(center_hub, hub_inner * 1.8, hub_inner * 1.8)

    def _draw_problem_zone(self, painter: QPainter) -> None:
        zone_center = QPointF(self.width() * 0.17, self.height() * 0.48)
        warm_glow = QRadialGradient(zone_center, self.width() * 0.18)
        warm_glow.setColorAt(0.0, QColor(255, 142, 88, 26))
        warm_glow.setColorAt(0.6, QColor(255, 98, 74, 10))
        warm_glow.setColorAt(1.0, QColor(255, 98, 74, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(warm_glow)
        painter.drawEllipse(zone_center, self.width() * 0.18, self.width() * 0.18)

        painter.setPen(QPen(QColor(255, 128, 106, 34), 1.2, Qt.PenStyle.DashLine))
        for idx in range(3):
            rect = QRectF(
                self.width() * 0.06 + idx * 24 + math.sin(self._phase * 0.10 + idx) * 6,
                self.height() * (0.22 + idx * 0.18),
                92 + idx * 10,
                68 + idx * 8,
            )
            painter.drawRoundedRect(rect, 16, 16)

        for idx in range(14):
            seed = idx * 0.62
            x = self.width() * 0.05 + self.width() * 0.18 * ((math.sin(self._phase * 0.16 + seed) + 1.0) / 2.0)
            y = self.height() * (0.22 + 0.038 * idx) + math.cos(self._phase * 0.22 + seed) * 8
            size = 2.4 + ((math.sin(self._phase * 0.34 + seed) + 1.0) / 2.0) * 3.8
            painter.setBrush(QColor(255, 162, 108, 34))
            painter.drawEllipse(QPointF(x, y), size, size)

    def _draw_solution_zone(self, painter: QPainter, center_hub: QPointF) -> None:
        for idx, radius in enumerate((26, 44, 66)):
            alpha = 26 + idx * 12
            pulse = radius + math.sin(self._phase * (0.22 + idx * 0.05) + idx) * 2.8
            painter.setPen(QPen(QColor(104, 214, 255, alpha), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center_hub, pulse, pulse)

        sweep_rect = QRectF(center_hub.x() - 86, center_hub.y() - 86, 172, 172)
        painter.setPen(QPen(QColor(118, 230, 255, 84), 3))
        start_angle = int(((self._phase * 42) % 360) * 16)
        painter.drawArc(sweep_rect, start_angle, 64 * 16)

        wedge_gradient = QRadialGradient(center_hub, 108)
        wedge_gradient.setColorAt(0.0, QColor(123, 219, 255, 34))
        wedge_gradient.setColorAt(0.65, QColor(123, 219, 255, 7))
        wedge_gradient.setColorAt(1.0, QColor(123, 219, 255, 0))
        painter.setBrush(wedge_gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_hub, 108, 108)

    def _draw_output_zone(self, painter: QPainter) -> None:
        zone_center = QPointF(self.width() * 0.82, self.height() * 0.48)
        cool_glow = QRadialGradient(zone_center, self.width() * 0.20)
        cool_glow.setColorAt(0.0, QColor(92, 205, 255, 26))
        cool_glow.setColorAt(0.58, QColor(92, 205, 255, 9))
        cool_glow.setColorAt(1.0, QColor(92, 205, 255, 0))
        painter.setBrush(cool_glow)
        painter.drawEllipse(zone_center, self.width() * 0.20, self.width() * 0.20)

        for idx in range(3):
            rect = QRectF(
                self.width() * 0.80 + idx * 14,
                self.height() * 0.34 + idx * 18,
                120,
                84,
            )
            painter.setBrush(QColor(255, 255, 255, 9 + idx * 3))
            painter.setPen(QPen(QColor(108, 232, 255, 18 + idx * 4), 1))
            painter.drawRoundedRect(rect, 18, 18)

    def _draw_light_reveal_layer(self, painter: QPainter) -> None:
        sweep_progress = (math.sin(self._phase * 0.065) + 1.0) / 2.0
        sweep_x = self.width() * (0.12 + 0.76 * sweep_progress)
        sweep_width = self.width() * 0.32
        sweep_gradient = QLinearGradient(sweep_x - sweep_width, 0, sweep_x + sweep_width, self.height())
        sweep_gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
        sweep_gradient.setColorAt(0.30, QColor(92, 188, 255, 0))
        sweep_gradient.setColorAt(0.50, QColor(106, 214, 255, 24))
        sweep_gradient.setColorAt(0.68, QColor(255, 255, 255, 8))
        sweep_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(sweep_gradient)
        painter.drawRect(self.rect())

        beams = [
            (self.width() * 0.28 + math.sin(self._phase * 0.12) * 30, self.height() * 0.34, 24, 450, -18, QColor(83, 198, 255, 40)),
            (self.width() * 0.60 + math.cos(self._phase * 0.10) * 28, self.height() * 0.50, 22, 500, 15, QColor(108, 128, 255, 28)),
            (self.width() * 0.76 + math.sin(self._phase * 0.08 + 1.4) * 24, self.height() * 0.30, 18, 300, 22, QColor(84, 239, 225, 30)),
        ]
        for center_x, center_y, beam_width, beam_height, angle, color in beams:
            painter.save()
            painter.translate(center_x, center_y)
            painter.rotate(angle)
            beam_rect = QRectF(-beam_width / 2, -beam_height / 2, beam_width, beam_height)
            beam_gradient = QLinearGradient(beam_rect.left(), beam_rect.top(), beam_rect.right(), beam_rect.top())
            beam_gradient.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 0))
            beam_gradient.setColorAt(0.5, color)
            beam_gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(beam_gradient)
            painter.drawRoundedRect(beam_rect, beam_width / 2, beam_width / 2)
            painter.restore()

        reveal_core = QPointF(
            self.width() * 0.55 + math.sin(self._phase * 0.07) * 32,
            self.height() * 0.44 + math.cos(self._phase * 0.09) * 18,
        )
        reveal_core_gradient = QRadialGradient(reveal_core, self.width() * 0.22)
        reveal_core_gradient.setColorAt(0.0, QColor(118, 206, 255, 46))
        reveal_core_gradient.setColorAt(0.52, QColor(118, 206, 255, 10))
        reveal_core_gradient.setColorAt(1.0, QColor(118, 206, 255, 0))
        painter.setBrush(reveal_core_gradient)
        painter.drawEllipse(reveal_core, self.width() * 0.22, self.width() * 0.22)

        hero_spot = QPointF(
            self.width() * 0.56 + math.sin(self._phase * 0.09) * 24,
            self.height() * 0.46 + math.cos(self._phase * 0.11) * 16,
        )
        spotlight = QRadialGradient(hero_spot, self.width() * 0.30)
        spotlight.setColorAt(0.0, QColor(94, 190, 255, 34))
        spotlight.setColorAt(0.55, QColor(94, 190, 255, 10))
        spotlight.setColorAt(1.0, QColor(94, 190, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(spotlight)
        painter.drawEllipse(hero_spot, self.width() * 0.30, self.width() * 0.30)

        reveal_wave = QLinearGradient(0, self.height() * 0.42, self.width(), self.height() * 0.58)
        reveal_wave.setColorAt(0.0, QColor(255, 255, 255, 0))
        reveal_wave.setColorAt(0.28, QColor(255, 255, 255, 5))
        reveal_wave.setColorAt(0.52, QColor(130, 226, 255, 16))
        reveal_wave.setColorAt(0.74, QColor(255, 255, 255, 4))
        reveal_wave.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(reveal_wave)
        painter.drawRect(self.rect())

        for index in range(4):
            curtain_x = sweep_x - 180 + index * 56 + math.sin(self._phase * 0.11 + index) * 8
            curtain_gradient = QLinearGradient(curtain_x, 0, curtain_x + 24, self.height())
            curtain_gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
            curtain_gradient.setColorAt(0.48, QColor(130, 226, 255, 6 + index * 2))
            curtain_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(curtain_gradient)
            painter.drawRect(QRectF(curtain_x, 0, 24, self.height()))

        top_shadow = QLinearGradient(0, 0, 0, self.height() * 0.34)
        top_shadow.setColorAt(0.0, QColor(0, 0, 0, 126))
        top_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(top_shadow)
        painter.drawRect(QRectF(0, 0, self.width(), self.height() * 0.34))

        bottom_shadow = QLinearGradient(0, self.height(), 0, self.height() * 0.62)
        bottom_shadow.setColorAt(0.0, QColor(0, 0, 0, 144))
        bottom_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(bottom_shadow)
        painter.drawRect(QRectF(0, self.height() * 0.62, self.width(), self.height() * 0.38))

        side_shadow = QLinearGradient(0, 0, self.width(), 0)
        side_shadow.setColorAt(0.0, QColor(0, 0, 0, 100))
        side_shadow.setColorAt(0.18, QColor(0, 0, 0, 26))
        side_shadow.setColorAt(0.54, QColor(0, 0, 0, 0))
        side_shadow.setColorAt(0.86, QColor(0, 0, 0, 18))
        side_shadow.setColorAt(1.0, QColor(0, 0, 0, 92))
        painter.setBrush(side_shadow)
        painter.drawRect(self.rect())

        edge_shadow = QRadialGradient(QPointF(self.width() * 0.52, self.height() * 0.52), self.width() * 0.78)
        edge_shadow.setColorAt(0.58, QColor(0, 0, 0, 0))
        edge_shadow.setColorAt(1.0, QColor(0, 0, 0, 108))
        painter.setBrush(edge_shadow)
        painter.drawRect(self.rect())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#081018"))

        glows = [
            (self.width() * 0.18, self.height() * 0.20, 300, QColor(37, 180, 255, 54)),
            (self.width() * 0.82, self.height() * 0.16, 280, QColor(91, 97, 255, 48)),
            (self.width() * 0.52, self.height() * 0.86, 360, QColor(28, 213, 176, 34)),
        ]
        for cx, cy, radius, color in glows:
            gradient = QRadialGradient(cx, cy, radius)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - radius), int(cy - radius), radius * 2, radius * 2)

        painter.setPen(QPen(QColor(100, 144, 210, 40), 1))
        for index in range(4):
            y = self.height() * (0.18 + index * 0.17) + math.sin(self._phase + index) * 6
            painter.drawLine(60, int(y), self.width() - 60, int(y))

        self._draw_storytelling_background(painter)
        self._draw_light_reveal_layer(painter)

        self._draw_floating_frame(painter, anchor_x=0.12, anchor_y=0.18, width=150, height=110, phase_offset=0.2, base_angle=-8, selected=False, variant="raw")
        self._draw_floating_frame(painter, anchor_x=0.86, anchor_y=0.18, width=154, height=112, phase_offset=1.6, base_angle=7, selected=False, variant="compare")
        self._draw_floating_frame(painter, anchor_x=0.16, anchor_y=0.82, width=172, height=120, phase_offset=2.1, base_angle=5, selected=False, variant="analyze")
        self._draw_floating_frame(painter, anchor_x=0.84, anchor_y=0.82, width=172, height=120, phase_offset=3.0, base_angle=-6, selected=False, variant="selected")

        super().paintEvent(event)
