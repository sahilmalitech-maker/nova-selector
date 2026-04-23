from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication


def apply_app_theme() -> None:
    font = QFont("Segoe UI", 10)
    QApplication.instance().setFont(font)


def build_stylesheet() -> str:
    return """
        QWidget {
            color: #eef2ff;
            selection-background-color: rgba(74, 155, 255, 0.32);
            selection-color: #ffffff;
        }
        QMainWindow {
            background: transparent;
        }
        #GlassCard, QFrame#AuthCenterCard, QFrame#MetricPill, QFrame#UserPanel, QFrame#ResultPanel {
            background: rgba(18, 24, 36, 0.90);
            border: 1px solid rgba(111, 148, 214, 0.18);
            border-radius: 22px;
        }
        QFrame#MetricPill {
            background: rgba(9, 14, 24, 0.78);
        }
        QLabel {
            background: transparent;
        }
        QLabel#AuthBrand, QLabel#SplashEyebrow, QLabel#PageEyebrow, QLabel#UserPanelCaption {
            color: #7fd4ff;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 1.7px;
            text-transform: uppercase;
        }
        QLabel#AuthTitle, QLabel#SplashTitle, QLabel#HeroTitle, QLabel#ProfileHeroTitle {
            color: #ffffff;
            font-size: 32px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }
        QLabel#AuthSubtitle, QLabel#SplashSubtitle, QLabel#HeroSubtitle, QLabel#CardSubtitle, QLabel#InlineHint, QLabel#ProfileInfoLabel, QLabel#AuthSupportText, QLabel#SplashTip, QLabel#UserMetaLabel {
            color: #9fb0ca;
            font-size: 13px;
            line-height: 1.45em;
        }
        QLabel#AuthValueHeadline, QLabel#SplashValue {
            color: #ffffff;
            font-size: 18px;
            font-weight: 600;
        }
        QLabel#CardTitle {
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
        }
        QLabel#StatusLabel, QLabel#SplashStatus, QLabel#AuthStatus, QLabel#AuthStatusError, QLabel#AuthStatusSuccess {
            font-size: 14px;
            font-weight: 600;
        }
        QLabel#AuthStatus {
            color: #eef2ff;
        }
        QLabel#AuthStatusError {
            color: #ffb0b0;
        }
        QLabel#AuthStatusSuccess {
            color: #9af2bc;
        }
        QLabel#EngineLabel {
            color: #9cc2ff;
            font-size: 13px;
            padding: 10px 14px;
            background: rgba(45, 85, 180, 0.20);
            border: 1px solid rgba(100, 150, 255, 0.20);
            border-radius: 12px;
        }
        QLabel#WarningLabel {
            color: #ffd691;
            font-size: 12px;
            padding: 10px 14px;
            background: rgba(157, 102, 17, 0.18);
            border: 1px solid rgba(255, 195, 100, 0.20);
            border-radius: 12px;
        }
        QLabel#MetricValue {
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
        }
        QLabel#MetricLabel, QLabel#ProfileInfoValue, QLabel#UserNameLabel {
            color: #ffffff;
            font-size: 15px;
            font-weight: 600;
        }
        QLabel#StatTitle {
            color: #9cabca;
            font-size: 12px;
            font-weight: 500;
        }
        QLabel#PhotoCountLabel {
            color: #7fd4ff;
            font-size: 16px;
            font-weight: 700;
            padding: 6px 10px;
            background: rgba(45, 85, 180, 0.20);
            border: 1px solid rgba(100, 150, 255, 0.20);
            border-radius: 10px;
        }
        QLabel#StatValue {
            color: #ffffff;
            font-size: 24px;
            font-weight: 700;
        }
        QLabel#AvatarLabel {
            background: rgba(16, 24, 38, 0.95);
            border: 1px solid rgba(122, 168, 245, 0.22);
            border-radius: 999px;
        }
        QLineEdit, QPlainTextEdit, QListWidget, QTextBrowser, QSpinBox, QDoubleSpinBox {
            background: rgba(9, 13, 22, 0.94);
            border: 1px solid rgba(112, 128, 170, 0.24);
            border-radius: 14px;
            padding: 12px 14px;
            color: #eef2ff;
        }
        QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QTextBrowser:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid rgba(87, 161, 255, 0.65);
        }
        QPlainTextEdit, QTextBrowser {
            padding: 14px;
        }
        QListWidget::item {
            padding: 8px 10px;
            margin: 2px 0;
            border-radius: 10px;
        }
        QListWidget::item:selected {
            background: rgba(77, 132, 255, 0.30);
            color: #ffffff;
        }
        QPushButton {
            border: 1px solid rgba(130, 149, 196, 0.22);
            border-radius: 14px;
            padding: 11px 18px;
            font-weight: 600;
            background: rgba(24, 32, 48, 0.96);
            color: #eef2ff;
        }
        QPushButton#SecondaryButton:hover {
            background: rgba(40, 53, 78, 1.0);
            border-color: rgba(130, 178, 255, 0.42);
        }
        QPushButton#SecondaryButton:pressed {
            background: rgba(18, 24, 36, 1.0);
        }
        QPushButton#AccentButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4e84ff, stop:0.58 #4b9cff, stop:1 #36d7ff);
            border: 1px solid rgba(102, 162, 255, 0.45);
            color: #ffffff;
        }
        QPushButton#AccentButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5c90ff, stop:0.58 #55a8ff, stop:1 #48ddff);
        }
        QPushButton:disabled {
            background: rgba(46, 54, 72, 0.72);
            color: rgba(232, 236, 248, 0.45);
            border-color: rgba(130, 149, 196, 0.12);
        }
        QProgressBar {
            border: 1px solid rgba(112, 128, 170, 0.24);
            border-radius: 9px;
            background: rgba(9, 13, 22, 0.94);
            text-align: center;
            color: #eef2ff;
        }
        QProgressBar::chunk {
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f85ff, stop:0.65 #32b3ff, stop:1 #5bf0ff);
        }
        QScrollArea {
            background: transparent;
            border: none;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 12px;
            margin: 4px;
        }
        QScrollBar::handle:vertical {
            background: rgba(93, 116, 172, 0.45);
            min-height: 26px;
            border-radius: 6px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QSplitter::handle {
            background: transparent;
        }
        #StatTile {
            background: rgba(9, 13, 22, 0.82);
            border: 1px solid rgba(112, 128, 170, 0.22);
            border-radius: 16px;
        }
    """
