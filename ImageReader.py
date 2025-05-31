import pytesseract
import config

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

class ImageReader:

    def text_from_img(self, image):
        text = pytesseract.image_to_string(image, lang="por", config='--oem 3 --psm 6')
        print(f"Tesseract text: \n\"{text}\"\n")
        return text

image_reader = ImageReader()
