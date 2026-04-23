from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout, QWidget

from .widgets import AnimatedButton


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("How Nova Image Scout Works")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        help_browser = QTextBrowser()
        help_browser.setOpenExternalLinks(True)
        help_browser.setHtml(
            """
            <h2>Nova Image Scout</h2>
            <p>A modern desktop tool for collecting the exact images you need from large libraries.</p>
            <h3>Workflow</h3>
            <ol>
              <li>Select a <b>Source Folder</b> that contains your image library.</li>
              <li>Select a <b>Destination Folder</b> where matches should be copied.</li>
              <li>Enter names or keywords in the text box. Use commas or new lines.</li>
              <li>Optional: import a screenshot for OCR, or add one or more reference images for visual search.</li>
              <li>Press <b>Start Smart Match</b>.</li>
            </ol>
            <h3>Photographer Culling AI</h3>
            <ol>
              <li>Select only a <b>Source Folder</b>, then press <b>Start Culling AI</b>.</li>
              <li>Nova evaluates every image through hard failure checks, technical quality, face/subject analysis, aesthetics, composition, context, and similar-image ranking.</li>
              <li>Results are grouped into final <b>SELECT</b> and <b>REJECT</b> decisions with duplicate suppression and photographer-style ranking.</li>
              <li>Double-click thumbnails to flip a frame between SELECT and REJECT, then press <b>Save Feedback + Learn</b> so future culls adapt to the client style.</li>
            </ol>
            <h3>Supported Matching Modes</h3>
            <ul>
              <li><b>Name Match:</b> ignores file extensions, is case-insensitive, and uses fuzzy matching for typos.</li>
              <li><b>OCR Input:</b> extracts text from a screenshot and auto-fills your query list.</li>
              <li><b>Visual Match:</b> compares reference images against the source library using CNN embeddings when available and keeps the strongest unique result for each reference.</li>
              <li><b>Culling AI:</b> ranks images like a decisive photographer, selects strong usable frames, and rejects weaker duplicates directly.</li>
            </ul>
            <h3>Supported File Types</h3>
            <p>JPG, JPEG, PNG, and WEBP.</p>
            <h3>Best Results</h3>
            <ul>
              <li>Use a slightly lower fuzzy threshold for typo-heavy lists.</li>
              <li>Use a higher visual threshold for stricter similarity.</li>
              <li>Install TensorFlow for the strongest MobileNetV2 visual matching pipeline.</li>
              <li>Install the local <b>Tesseract OCR</b> engine if OCR is not already available on your system.</li>
            </ul>
            """
        )
        close_button = AnimatedButton("Close")
        close_button.clicked.connect(self.accept)

        layout.addWidget(help_browser)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
