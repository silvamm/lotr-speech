import pytesseract
import config
import cv2 as cv

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

class ImageReader:

    def text_from_img(self, image):
        image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        text = pytesseract.image_to_string(image, lang="por", config='--oem 3 --psm 6')
        print(f"Tesseract text: \n\"{text}\"\n")
        return text

image_reader = ImageReader()
