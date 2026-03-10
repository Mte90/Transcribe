#!/usr/bin/env python
import sys
import os
import json
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTextEdit, QMessageBox,
    QFileDialog, QFrame, QDialog, QLineEdit, QComboBox, QFormLayout,
    QDialogButtonBox, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent

from pydub import AudioSegment

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.m4a', '.mp3', '.wav', '.ogg', '.webm'}

# 18 European languages
LANGUAGES = {
    'it': 'Italiano',
    'en': 'English',
    'de': 'Deutsch',
    'fr': 'Français',
    'es': 'Español',
    'pt': 'Português',
    'nl': 'Nederlands',
    'pl': 'Polski',
    'ru': 'Русский',
    'uk': 'Українська',
    'cs': 'Čeština',
    'ro': 'Română',
    'hu': 'Magyar',
    'el': 'Ελληνικά',
    'sv': 'Svenska',
    'da': 'Dansk',
    'fi': 'Suomi',
    'no': 'Norsk',
}

# Constants
CHUNK_DURATION_MS = 2 * 60 * 1000
CHUNKS_DIR = "/tmp/audio_chunks"


def has_repeated_phrases(text, window_size=20, threshold=2):
    """Check if text has repeated phrases indicating transcription issues."""
    words = text.strip().split()
    if len(words) < window_size:
        return False
    tail = words[-window_size:]
    phrases = [' '.join(tail[i:i+5]) for i in range(len(tail) - 4)]
    count = {}
    for phrase in phrases:
        count[phrase] = count.get(phrase, 0) + 1
        if count[phrase] >= threshold:
            return True
    return False


def remove_repeated_sentences(text, chunk_index):
    """Remove duplicate consecutive sentences from transcription."""
    sentences = [s.strip() for s in text.strip().split('.') if s.strip()]
    result = []

    for i, sentence in enumerate(sentences):
        if i == 0 or sentence != sentences[i - 1]:
            result.append(sentence)

    return '. '.join(result) + '.'


def convert_and_split_audio(input_path, chunk_duration_ms, output_dir):
    """Convert audio/video file and split into chunks."""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError("pydub is required. Install with: pip install pydub")
    
    os.makedirs(output_dir, exist_ok=True)
    audio = AudioSegment.from_file(input_path)
    chunks = []
    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_path = os.path.join(output_dir, f"chunk_{i // chunk_duration_ms}.ogg")
        chunk.export(chunk_path, format="ogg")
        chunks.append(chunk_path)
    return chunks


def transcribe_audio_with_check(file_path, chunk_index, api_key, base_url, language):
    """Transcribe a single audio chunk with retry logic using REST API."""
    url = f"{base_url}audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    duration = 0
    transcript = ""
    
    for attempt in range(1, 4):
        try:
            with open(file_path, "rb") as audio_file:
                files = {"file": (os.path.basename(file_path), audio_file, "audio/ogg")}
                data = {
                    "model": "faster-whisper-large-v3",
                    "language": language,
                    "response_format": "json"
                }
                
                response = requests.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                
                try:
                    result = response.json()
                    if isinstance(result, dict):
                        transcript = result.get("text", "").strip()
                        duration = result.get("duration", 0)
                    else:
                        transcript = response.text.strip()
                        duration = 0
                except json.JSONDecodeError:
                    transcript = response.text.strip()
                    duration = 0
                    
        except requests.exceptions.RequestException as e:
            if attempt < 3:
                continue
            raise Exception(f"Request failed after 3 attempts: {e}")
        
        if not has_repeated_phrases(transcript):
            return transcript, duration
    
    trimmed = remove_repeated_sentences(transcript, chunk_index)
    return trimmed, duration


class SettingsDialog(QDialog):
    """Dialog for configuring API settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Configuration")
        self.setMinimumSize(400, 200)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QFormLayout(self)
        
        # API Endpoint
        self.endpoint_input = QLineEdit()
        layout.addRow("API Endpoint:", self.endpoint_input)
        
        # API Key with show/hide toggle
        key_layout = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_button = QPushButton("Show")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setMinimumWidth(60)
        self.toggle_button.toggled.connect(self._on_api_key_toggle)
        key_layout.addWidget(self.key_input)
        key_layout.addWidget(self.toggle_button)
        layout.addRow("API Key:", key_layout)
        
        # Language selection
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        layout.addRow("Default Language:", self.language_combo)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)
    
    def _on_api_key_toggle(self, checked: bool):
        if checked:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def load_settings(self, settings):
        """Load settings from QSettings."""
        self.endpoint_input.setText(settings.value("api/endpoint", "https://api.regolo.ai/v1/"))
        self.key_input.setText(settings.value("api/key", ""))
        saved_language = settings.value("language", "it")
        default_index = self.language_combo.findData(saved_language)
        if default_index >= 0:
            self.language_combo.setCurrentIndex(default_index)
    
    def save_settings(self, settings):
        """Save settings to QSettings."""
        settings.setValue("api/endpoint", self.endpoint_input.text())
        settings.setValue("api/key", self.key_input.text())
        settings.setValue("language", self.language_combo.currentData())


class TranscriptionWorker(QThread):
    """Worker thread for audio transcription."""
    
    progress = pyqtSignal(int, int, str)  # current_chunk, total_chunks, message
    finished = pyqtSignal(str, float)  # full transcription, total duration
    error = pyqtSignal(str)  # error message
    
    def __init__(self, input_file, api_key, base_url, language):
        super().__init__()
        self.input_file = input_file
        self.api_key = api_key
        self.base_url = base_url
        self.language = language
    
    def run(self):
        try:
            # Convert and split audio
            self.progress.emit(0, 0, "Converting and splitting audio...")
            chunk_files = convert_and_split_audio(
                self.input_file, CHUNK_DURATION_MS, CHUNKS_DIR
            )
            
            if not chunk_files:
                self.error.emit("No audio chunks were created.")
                return
            
            # Transcribe each chunk
            full_transcription = ""
            total_duration = 0.0
            total_chunks = len(chunk_files)
            
            for idx, chunk_path in enumerate(chunk_files):
                self.progress.emit(
                    idx + 1, total_chunks,
                    f"Transcribing chunk {idx + 1} of {total_chunks}..."
                )
                try:
                    transcript, chunk_duration = transcribe_audio_with_check(
                        chunk_path, idx, self.api_key, self.base_url, self.language
                    )
                    full_transcription += transcript + "\n"
                    total_duration += chunk_duration
                except Exception as e:
                    self.error.emit(f"Error transcribing chunk {idx + 1}: {e}")
                    return
            
            self.finished.emit(full_transcription.strip(), total_duration)
            
        except Exception as e:
            self.error.emit(f"Transcription error: {e}")


class DropArea(QFrame):
    """Custom widget for drag & drop file selection."""
    
    file_dropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Drop video/audio file here\nor click to browse")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        
        # Style
        self.setStyleSheet("""
            DropArea {
                border: 2px dashed #888;
                border-radius: 8px;
                background-color: #f5f5f5;
            }
            DropArea:hover {
                border-color: #555;
                background-color: #ebebeb;
            }
            QLabel {
                font-size: 14px;
                color: #555;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.styleSheet().replace("#f5f5f5", "#e0e0e0"))
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("#e0e0e0", "#f5f5f5"))
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(self.styleSheet().replace("#e0e0e0", "#f5f5f5"))
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                self.file_dropped.emit(file_path)
            else:
                self.file_dropped.emit("")
    
    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio/Video File",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.m4a *.mp3 *.wav *.ogg *.webm)"
        )
        if file_path:
            self.file_dropped.emit(file_path)


class TranscribeWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcribe")
        self.setMinimumSize(800, 600)
        
        # Initialize QSettings
        self.settings = QSettings("TranscribeApp", "TranscribeGUI")
        
        self.selected_file = None
        self.worker = None
        
        self._setup_menubar()
        self._setup_ui()
    
    def _setup_menubar(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        
        config_action = QAction("API Configuration...", self)
        config_action.triggered.connect(self._open_settings)
        settings_menu.addAction(config_action)
    
    def _setup_ui(self):
        """Create and arrange UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Drop area
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self._on_file_dropped)
        layout.addWidget(self.drop_area)
        
        # File path label
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.file_label)
        
        # Language selector
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        saved_language = self.settings.value("language", "it")
        default_index = self.language_combo.findData(saved_language)
        if default_index >= 0:
            self.language_combo.setCurrentIndex(default_index)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        layout.addWidget(self.language_combo)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Duration label
        self.duration_label = QLabel("")
        self.duration_label.setStyleSheet("color: #666; font-style: italic;")
        self.duration_label.setVisible(False)
        layout.addWidget(self.duration_label)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #555;")
        layout.addWidget(self.status_label)
        
        # Start button
        self.start_button = QPushButton("Start Transcription")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self._start_transcription)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
            QPushButton:disabled {
                background-color: #b0b0b0;
            }
        """)
        layout.addWidget(self.start_button)
        
        # Transcription text area
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Transcription will appear here...")
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_edit, 1)
        
        # Save button
        self.save_button = QPushButton("Save Transcription")
        self.save_button.setEnabled(False)
        self.save_button.setMinimumHeight(35)
        self.save_button.clicked.connect(self._save_transcription)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
            QPushButton:disabled {
                background-color: #b0b0b0;
            }
        """)
        layout.addWidget(self.save_button)
    
    def _on_language_changed(self, index):
        """Handle language selection change."""
        self.settings.setValue("language", self.language_combo.itemData(index))
    
    def _open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        dialog.load_settings(self.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save_settings(self.settings)
    
    def _on_file_dropped(self, file_path):
        """Handle file selection via drag & drop or file dialog."""
        if not file_path:
            QMessageBox.warning(
                self,
                "Invalid File",
                "Please select a valid audio or video file.\n\n"
                f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
            )
            return
        
        self.selected_file = file_path
        display_path = file_path
        if len(display_path) > 60:
            display_path = "..." + display_path[-57:]
        self.file_label.setText(f"Selected: {display_path}")
        self.file_label.setStyleSheet("color: #333; font-weight: bold;")
        self.start_button.setEnabled(True)
    
    def _start_transcription(self):
        """Start the transcription process."""
        if not self.selected_file:
            return
        
        # Get settings
        api_key = self.settings.value("api/key", "")
        base_url = self.settings.value("api/endpoint", "https://api.regolo.ai/v1/")
        language = self.settings.value("language", "it")
        
        if not api_key:
            QMessageBox.warning(
                self,
                "API Key Required",
                "Please configure your API key in Settings (Settings → API Configuration) before starting transcription."
            )
            return
        
        self.start_button.setEnabled(False)
        self.drop_area.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.text_edit.clear()
        self.duration_label.setVisible(False)
        self.status_label.setText("Starting transcription...")
        
        # Create and start worker thread
        self.worker = TranscriptionWorker(self.selected_file, api_key, base_url, language)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_progress(self, current, total, message):
        """Update progress bar and status."""
        self.status_label.setText(message)
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
    
    def _on_finished(self, transcription, duration):
        """Handle successful transcription."""
        self.text_edit.setPlainText(transcription)
        self.status_label.setText("Transcription complete!")
        self.duration_label.setText(f"Duration: {duration:.1f}s")
        self.duration_label.setVisible(True)
        self.progress_bar.setVisible(False)
        self.start_button.setEnabled(True)
        self.drop_area.setEnabled(True)
        self.save_button.setEnabled(True)
        self.worker = None
    
    def _on_error(self, error_message):
        """Handle transcription error."""
        QMessageBox.critical(self, "Transcription Error", error_message)
        self.status_label.setText("Transcription failed.")
        self.progress_bar.setVisible(False)
        self.start_button.setEnabled(True)
        self.drop_area.setEnabled(True)
        self.worker = None
    
    def _save_transcription(self):
        """Save transcription to a file."""
        text = self.text_edit.toPlainText()
        if not text:
            return
        
        default_name = "transcription.txt"
        if self.selected_file:
            base = os.path.splitext(os.path.basename(self.selected_file))[0]
            default_name = f"{base}_transcription.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Transcription",
            default_name,
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Transcription saved to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Save Error",
                    f"Failed to save file:\n{e}"
                )
    
    def closeEvent(self, event):
        """Clean up worker thread on close."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = TranscribeWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
