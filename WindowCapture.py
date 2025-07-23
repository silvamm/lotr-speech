import numpy as np
import win32con
import win32gui
import win32ui

import mss
import numpy as np

class WindowCaptureMSS:
    def __init__(self):
        self.monitor = {"top": 150, "left": 350, "width": 1250, "height": 700}
        self.sct = mss.mss()

    def get_screenshot(self):
        sct_img = self.sct.grab(self.monitor)
        img = np.array(sct_img)
        img = img[..., :3]  # remove alpha
        return img


class WindowCapture:
    hwnd = None
    x = 350
    y = 150
    width = 1250
    height = 700
    
    def __init__(self):
        self.hwnd = win32gui.GetDesktopWindow()
      

    def get_screenshot(self):

        # get the window image data
        self.w_dc = win32gui.GetWindowDC(self.hwnd)
        dc_obj = win32ui.CreateDCFromHandle(self.w_dc)
        c_dc = dc_obj.CreateCompatibleDC()
        data_bit_map = win32ui.CreateBitmap()
        data_bit_map.CreateCompatibleBitmap(dc_obj, self.width, self.height)
        c_dc.SelectObject(data_bit_map)

        c_dc.BitBlt((0, 0), (self.width, self.height), dc_obj, (self.x, self.y), win32con.SRCCOPY)

        # convert the raw data into a format opencv can read
        signed_ints_array = data_bit_map.GetBitmapBits(True)
        img = np.frombuffer(signed_ints_array, dtype='uint8')
        img.shape = (self.height, self.width, 4)

        # free resources
        dc_obj.DeleteDC()
        c_dc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, self.w_dc)
        win32gui.DeleteObject(data_bit_map.GetHandle())

        # drop the alpha channel, or cv.matchTemplate() will throw an error like:
        #   error: (-215:Assertion failed) (depth == CV_8U || depth == CV_32F) && type == _templ.type()
        #   && _img.dims() <= 2 in function 'cv::matchTemplate'
        img = img[..., :3]

        # make image C_CONTIGUOUS to avoid errors that look like:
        #   File ... in draw_rectangles
        #   TypeError: an integer is required (got type tuple)
        # see the discussion here:
        # https://github.com/opencv/opencv/issues/14866#issuecomment-580207109
        img = np.ascontiguousarray(img)

        return img
