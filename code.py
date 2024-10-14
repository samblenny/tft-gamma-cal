# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Hardware:
# - Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM (#5483)
#
# Pinouts:
# | TFT feather | ST7789 TFT |
# | ----------- | ---------- |
# |  SCK        |  SCK       |
# |  MOSI       |  MOSI      |
# |  MISO       |  MISO      |
# |  TFT_CS     |  CS        |
# |  TFT_DC     |  DC        |
#
# Related Documentation:
# - https://learn.adafruit.com/adafruit-esp32-s3-tft-feather
# - https://learn.adafruit.com/adafruit-1-14-240x135-color-tft-breakout
# - https://docs.circuitpython.org/en/latest/shared-bindings/displayio/
# - https://docs.circuitpython.org/projects/display_text/en/latest/api.html
# - https://learn.adafruit.com/circuitpython-display_text-library?view=all
#
import board
from digitalio import DigitalInOut, Direction
from displayio import Bitmap, Group, Palette, TileGrid, release_displays
from fourwire import FourWire
import gc
from micropython import const
from terminalio import FONT
import time

from adafruit_display_text import bitmap_label
from adafruit_st7789 import ST7789


class GammaCurve:

    # Preset 7-point calibration curves for some common gamma profiles. Some of
    # these numbers come from my gamma curve checker web tool (see index.html)
    BLACK = 0   # index into PRESETS for black
    WHITE = 1   # index into PRESETS for white
    PRESETS = {
        #             black white  1/2  1/4  1/8  1/16  1/32  1/64  1/128
        "FeatherTFT": (  0,  255,  196, 148, 104,   64,   36,   16,     8),
        "sRGB-ish":   (  0,  255,  171, 127,  97,   74,   56,   41,    30),
        "2020's-P3":  (  0,  255,  185, 135,  97,   71,   51,   36,    27),
        "2010's-TFT": (  0,  255,  184, 131,  94,   68,   50,   36,    28),
    }

    def __init__(self):
        # Initialize the gamma curve test pattern
        self.curve = list(self.PRESETS["FeatherTFT"])
        self.palette = Palette(len(self.curve))
        self.bars = len(self.curve) - 2  # omit black, omit white
        self._update_palette()
        self.selection = self.WHITE + 1  # start at index for 1/2 brightness

    def load_preset(self, key):
        # Attempt to load argument key as a gamma curve preset.
        # Returns True if it worked or False if key is not a preset name
        if not key in self.PRESETS:
            return False
        else:
            return True

    def _update_palette(self):
        # Update 24-bit colors in palette to match 8-bit gray values of curve.
        for (i, gray) in enumerate(self.curve):
            self.palette[i] = (gray << 16) | (gray << 8) | gray

    def set_gray(self, n):
        # Change the value of the currently selected 8-bit gray point.
        if not (0 < n < 255):
            raise Exception(f"gray value is out of range: {n}")
        self.curve[self.selection] = n
        self._update_palette()

    def next_graypoint(self):
        # Select next graypoint, skipping first (white) and last (black).
        n = self.selection - 2
        self.selection = self.WHITE + 1 + ((n + 1) % self.bars)

    def prev_graypoint(self):
        # Select previous graypoint, skipping first (white) and last (black).
        n = self.selection - 2
        self.selection = self.WHITE + 1 + ((n - 1) % self.bars)

    def __str__(self):
        # Return printable string for this gamma curve (omit white and black).
        s = self.selection
        curve = self.curve
        # build string with stars around current selected graypoint
        left  = ''.join(['%03d   ' % n for n in curve[self.WHITE+1:s]])
        sel   = '%03d<' % curve[s]
        right = ''.join(['  %03d ' % n for n in curve[s+1:]])
        return '%s%s%s' % (left, sel, right)


def main():
    # This function has initialization code and the main event loop. Under
    # normal circumstances, this function does not return.

    # Prepare to use the Feather TFT's built in  ST7789 display with native
    # display size of 240x135px.
    TFT_W = const(240)
    TFT_H = const(135)
    display = board.DISPLAY
    gc.collect()

    # Make a gamma curve object which includes a .palette property which we
    # will need for making a TileGrid later
    gamma_curve = GammaCurve()

    # Make a bitmap for the gamma calibration pattern
    #
    # The pattern has 7 vertical bars. The top half of each bar is made from a
    # checkerboard dither pattern. The bottom half of each bar is a solid
    # color. Because human eyes are tricky, if the gamma curve values are
    # adjusted right, the top and bottom half of each bar will appear to be the
    # same hue and value.
    #
    # The bitmap's pattern of indexed colors for the dithered and solid grays
    # looks kinda like this, but scaled up:
    #
    #    0101 0202 0303 0404 0505 0606 0707  \   upper half of each bars is
    #    1010 2020 3030 4040 5050 6060 7070   }  dithered in a checkerboard
    #    0101 0202 0303 0404 0505 0606 0707  /   pattern
    #
    #    2222 3333 4444 5555 6666 7777 8888  \
    #    2222 3333 4444 5555 6666 7777 8888   }  lower halves are solid gray
    #    2222 3333 4444 5555 6666 7777 8888  /
    #     ^    ^    ^    ^    ^    ^    ^
    #    1/2  1/4  1/8  1/16 1/32 1/64 1/128
    #
    #  Note that palette index 0 is white, 1..6 are grays, and 7 is black.
    #
    PAD = const(30)
    width = TFT_W
    height = TFT_H - PAD
    bmp = Bitmap(width, height, len(gamma_curve.palette))
    middle = height // 2
    number_of_bars = gamma_curve.bars
    px_per_bar = TFT_W // number_of_bars
    for y in range(bmp.height):
        for x in range(bmp.width // number_of_bars * number_of_bars):
            # Select palette colors for the dither pattern based on the current
            # x coordinate. Palette[0] is white, Palette[1] is the 1/2
            # brightness gray value, Palette[2] is 1/4 brightness, etc.
            which_vertical_bar = x // px_per_bar
            # Dark dither color is always black
            dark = gamma_curve.BLACK
            # Light dither color is white for the leftmost bar. Then, for each
            # bar to the right, it takes the value of the solid gray color from
            # the previous (one step lighter/to-the-left) gray bar.
            light = gamma_curve.WHITE + which_vertical_bar
            solid = light + 1
            if y < middle:
                dither_light = (x ^ y) & 1
                bmp[x, y] = light if dither_light else dark
            else:
                bmp[x, y] = solid

    # Combine the bitmap and palette into a TileGrid
    test_pattern = TileGrid(bmp, pixel_shader=gamma_curve.palette, x=0, y=PAD)

    # Make a text label for status messages
    status = bitmap_label.Label(FONT, text="", color=0xFF0000, scale=1)
    status.anchor_point = (0, 0)
    status.anchored_position = (0, 0)

    # Arrange TileGrid and label into the root group
    grp = Group(scale=1)
    grp.append(test_pattern)
    grp.append(status)
    display.root_group = grp

    # MAIN EVENT LOOP
    help_message = """
============================
=== TFT Gamma Calibrator ===
============================

Your goal is to adjust the brightness value of the bottom half of each gray bar
shown on the Feather TFT's display to match the top half. Begin with the
leftmost bar, which is a 50% dither of 0x000000 (black) and 0xFFFFFF (white).

Commands:

  1..254   set selected graypoint to an 8-bit integer gray value
       n   select Next graypoint
       p   select Previous graypoint
       ?   show this help message
"""
    print(help_message)
    waiting_on_serial_input = True
    while True:
        curve_txt = str(gamma_curve)
        if waiting_on_serial_input:
            status.text = 'CHECK SERIAL CONSOLE\n%s' % curve_txt
        else:
            status.text = '\n%s' % curve_txt
        time.sleep(0.1)
        # Prompt for a new grayscale value
        ans = input('[%s]: ' % curve_txt)
        waiting_on_serial_input = False
        try:
            n = int(ans)
            if 0 < n < 255:
                # If answer was an in-range grayscale value, change the value
                gamma_curve.set_gray(n)
            else:
                print("gray value out of range")
        except ValueError as e:
            if ans == 'n':                    # "n" for next curve point
                gamma_curve.next_graypoint()
            elif ans == 'p':                  # "p" for previous curve point
                gamma_curve.prev_graypoint()
            elif ans == '?':                  # "?" for help
                print(help_message)
            elif ans == '':                   # ignore ""
                pass
            else:
                print('eh, what? (for help, try "?")')


main()
