# lotr-speech - readme - wip

I'm using OpenCV and Tesseract OCR to detect text within the game and convert images to text, respectively. The extracted text is then sent to OpenAI for narration. Between this main flow, there are several optimizations to improve performance and efficiency. The project is currently focused on Brazilian Portuguese.
To reduce costs, generated audio files are saved and reused whenever the same text appears again. These records are stored in a SQLite database

## Main Features
- Uses the latest OpenAI TTS model, providing a much more immersive and natural reading experience

- Streams audio playback before saving: Instead of waiting for the full audio to be generated before playback, this project starts streaming the audio immediately, ensuring a faster and smoother experience. The audio is then saved in the background for future reuse

- Implements a smart caching system: previously generated audios are saved and reused when the same text appears again (which happens frequently with UI elements like interaction icons). This makes repeated playback almost instant — and helps save money on API usage

- Optional one-time reading mechanism: You can configure the system to read each piece of text only once, helping avoid unnecessary repetition and improving overall flow

## Requirements

- **Python 3.10 or higher**  
   Download: [python.org/downloads](https://www.python.org/downloads/)

- **Tesseract OCR**  
   Install guide: [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)

- **OpenAI API Account**

   This project requires an OpenAI API key to use text-to-speech feature. To get started, you need to:

   Create an account at https://openai.com/api/

   Obtain an API key from your account dashboard

   Make sure you have some credits available 

## Installation

Clone the repository and install dependencies

## Configuration

To use your language, you need to download the corresponding .traineddata file and copy it to the tessdata folder inside your Tesseract installation path. For example, here is the Portuguese trained data file:
https://github.com/tesseract-ocr/tessdata/blob/master/por.traineddata



Create a file named `config.py` in the root directory of the project and add the following content:

```python
DEBUG_MODE = False
SPEECH_HISTORY_SIZE_LIMIT = 20 
PLAY_AUDIOS = True 
SAVE_AUDIOS_DB = True
SAVE_AUDIOS = True

TESSERACT_PATH = r"C:\Path\To\tesseract.exe"	# Example: C:\Program Files\Tesseract-OCR\tesseract.exe
OPENAI_API_KEY = "your-api-key-here"
```

## Thanks To

This project is inspired by:  
https://github.com/rpiotrow96/LOTR-Lector

## Other Projects

### Mage Knight - Solo Table

https://silvamm.github.io/mage-knight-solo-table/

https://github.com/silvamm/mage-knight-solo-table

### Arkham Horror Card Game - Helper

https://silvamm.github.io/arkham-horror-card-game-helper/