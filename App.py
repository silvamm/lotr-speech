import time
import sys 
import signal
from ImageCropper import ImageCropper
from datetime import datetime
from WindowCapture import WindowCapture
from TextReader import text_reader
from ImageReader import image_reader

class App:

    def run(self):
        print("lotr-speech has started")
        window_capture = WindowCapture()
        image_cropper = ImageCropper()
        session_time = 'Session started: {}'.format(datetime.today())

        text_read = False
        self.attach(text_reader)

        while True:
            loop_time = time.time()

            screenshot = window_capture.get_screenshot()
            found_img, max_loc = image_cropper.find_image_boost(screenshot)

            #If I change the screen or click the cancel button, we should stop reading      
            if found_img is False:
                self.set_variavel(found_img)
                text_read = False

            #I start looking for images to read if I don't have one and I'm not currently reading
            if found_img and text_read is False:
                print('#'*100)

                # wait until the whole border appears
                time.sleep(0.2)

                screenshot = window_capture.get_screenshot()
                screenshot_time = 'Screenshot time: {:.4f}'.format(time.time() - loop_time)
                #cv.imwrite('screenshot.jpg', screenshot)

                screenshot, crop_img = image_cropper.crop_image(screenshot, max_loc)
                crop_time = 'Crop time: {:.4f}'.format(time.time() - loop_time)
                #cv.imwrite('result.jpg', crop_img)
                
                text = image_reader.text_from_img(crop_img)
                pytesseract_read_time = 'Tesseract read time: {:.4f}'.format(time.time() - loop_time)

                text_reader.speech(text)
                text_read = True
                
                print(screenshot_time)
                print(crop_time)
                print(pytesseract_read_time)
                print(session_time)

                

    def signal_handler(sig, frame):
        sys.exit(0)  

    signal.signal(signal.SIGINT, signal_handler)

    def __init__(self):
        self._observers = []
        self._found_image = False

    def attach(self, observer):
        self._observers.append(observer)

    def detach(self, observer):
        self._observers.remove(observer)

    def set_variavel(self, value):
        self._found_image = value
        self._notify()

    def _notify(self):
        for observer in self._observers:
            observer.update(self._found_image)