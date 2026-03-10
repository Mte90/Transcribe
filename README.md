# Transcribe GUI
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)   

Desktop application for audio/video transcription using REST API.

<img width="800" height="623" alt="Image" src="https://github.com/user-attachments/assets/18c7102e-1811-4135-a36b-3d6519e0e416" />

## Installation

```bash
pip install pydub PyQt6 requests
```

## Usage

1. Run the application:
   ```bash
   python transcribe_gui.py
   ```

2. Configure API settings:
   - Go to **Settings → API Configuration**
   - Enter your API endpoint and key
   - Select default language

3. Drop an audio/video file or click to browse

4. Click **Start Transcription**

5. Save the transcription when complete

## Supported Formats

- Video: `.mp4`, `.mkv`, `.avi`, `.webm`
- Audio: `.m4a`, `.mp3`, `.wav`, `.ogg`

## Supported Languages (18 European languages)

Italiano, English, Deutsch, Français, Español, Português, Nederlands, Polski, Русский, Українська, Čeština, Română, Magyar, Ελληνικά, Svenska, Dansk, Suomi, Norsk
