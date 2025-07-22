import cv2 as cv

class ImageCropper:
    border = None
    threshold = 0.9
    debug = False

    def __init__(self):
        self.border = cv.imread('border.PNG', cv.IMREAD_UNCHANGED)

    def find_image(self, haystack_img):
        result_bottom = cv.matchTemplate(haystack_img,  self.border, cv.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result_bottom)
        if max_val > self.threshold:
            return True, max_loc
        return False, None
    
    def find_image_boost(self, haystack_img):
        scale_percent = 50

        # Convert to grayscale
        if haystack_img.ndim == 3:
            haystack_gray = cv.cvtColor(haystack_img, cv.COLOR_BGR2GRAY)
        else:
            haystack_gray = haystack_img

        if self.border.ndim == 3:
            border_gray = cv.cvtColor(self.border, cv.COLOR_BGR2GRAY)
        else:
            border_gray = self.border

        # Resize for speed
        haystack_small = cv.resize(haystack_gray, None, fx=scale_percent/100, fy=scale_percent/100, interpolation=cv.INTER_NEAREST)
        border_small = cv.resize(border_gray, None, fx=scale_percent/100, fy=scale_percent/100, interpolation=cv.INTER_NEAREST)

        # Match template
        result = cv.matchTemplate(haystack_small, border_small, cv.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)

        if max_val > self.threshold:
            x = int(max_loc[0] * (100 / scale_percent))
            y = int(max_loc[1] * (100 / scale_percent))
            return True, (x, y)

        return False, None

    def crop_image(self, haystack_img, max_loc):
        needle_w = self.border.shape[1]
        needle_h = self.border.shape[0]

        # top left always at 0,0
        top_left = (0, 0)
        bottom_right = (max_loc[0] + needle_w, max_loc[1] + needle_h)
       
        #cv.rectangle(haystack_img, top_left, bottom_right, color=(0, 255, 0), thickness=2, lineType=cv.LINE_4)
      
        margin = 20
        x = top_left[0] + margin
        y = top_left[1] + margin
        h = bottom_right[1] - (top_left[1] + 2 * margin)
        w = bottom_right[0] - (top_left[0] + 2 * margin)

        cropped_img = haystack_img[y:y + h, x:x + w]

        if cropped_img.size == 0:
            cropped_img = None
            return haystack_img, cropped_img
        
        #with ThreadPoolExecutor() as executor:
        #    executor.map(lambda func: replace_symbol_parallel(func, cropped_img), replace_funcs)

        return haystack_img, cropped_img
