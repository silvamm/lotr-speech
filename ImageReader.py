import pytesseract
import config
import cv2 as cv
from PIL import Image as PILImage
import tesserocr

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

class ImageReader:

    def text_from_img(self, image):
        image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(image, lang="por", config='--oem 3 --psm 6')
        print(f"Tesseract text: \n\"{text}\"\n")
        return text
    
    def text_from_img_boost(self, image):
        # Conversão de BGR para RGB
        image_rgb = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        pil_image = PILImage.fromarray(image_rgb)

        # Reconhecimento
        with tesserocr.PyTessBaseAPI(lang='por', psm=6, oem=3) as api:
            api.SetImage(pil_image)
            text = api.GetUTF8Text()
            print(f"Tesserocr text: \n\"{text}\"\n")
            return text

image_reader = ImageReader()
