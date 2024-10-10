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
from board import SPI, TFT_CS, TFT_DC
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

    # These are state machine state constants for the order of finding
    # calibration points. To begin with, all we know for sure is that the
    # display's black is 0x000000 and its white is 0xFFFFFF. By comparing to
    # a 50% dither of black with white, we can find the color code that will
    # be perceived as 50% gray (matching the dither pattern's brightness).
    # Once we know the code for 50% gray, we can find 25% and 75% gray by
    # comparing to a dithers of black with 50% gray and white with 50% gray.
    # The same method can find values for 12%, 25%, 37%, 62%, and 87% gray.
    #
    GRAY00 = const(0)  # black (zero reference value)
    GRAY50 = const(1)  # == 50% dither of black with white
    GRAY25 = const(2)  # == 50% dither of black with GRAY50 value
    GRAY75 = const(3)  # == 50% dither of GRAY50 value with white
    GRAY12 = const(4)  # == 50% dither of black with GRAY25 value
    GRAY87 = const(5)  # == 50% dither of GRAY75 value with white
    GRAY37 = const(6)  # == 50% dither of GRAY25 value with GRAY50 value
    GRAY62 = const(7)  # == 50% dither of GRAY50 value with GRAY75 value
    GRAY99 = const(8)  # white (full-scale reference value)

    # This lookup table lets us get from state machine state constants to the
    # corresponding indexes of the gamma correction curve.
    LUT = {
        GRAY00: 0,  # black
        GRAY12: 1,
        GRAY25: 2,
        GRAY37: 3,
        GRAY50: 4,  # same brightness as 50% dither of black with white
        GRAY62: 5,
        GRAY75: 6,
        GRAY87: 7,
        GRAY99: 8,  # white
    }

    def __init__(self):
        # Initialize with a GRAY50 selected and a linear correction curve
        self.state = GRAY50
        self.curve = [0, 7, 15, 23, 31, 39, 47, 55, 63]
        self.dither_dark  = self.curve[self.LUT[GRAY00]]
        self.dither_light = self.curve[self.LUT[GRAY99]]

    def set_gray6(self, n):
        # Change the value of the currently selected 6-bit gray state. Gray
        # value argument, n, must be in range 1..62 (excludes white and black).
        if not (0 < n < 63):
            raise Exception(f"set_gray({n}): gray value is out of range")
        self.curve[self.LUT[self.state]] = n

    def update_palette3(self, palette):
        # Set the colors of the 3-color displayio.Palette argument, palette, to
        # 24-bit color values corresponding to dither_dark, dither_light, and
        # the currently selected graypoint, in that order.

        # Make an anonymous function to convert 6-bit gray to 24-bit RGB
        _6to24 = lambda n: ((n << 2) << 16) | ((n << 2) << 8) | (n << 2)

        palette[0] = _6to24(self.dither_dark)
        palette[1] = _6to24(self.dither_light)
        palette[2] = _6to24(self.curve[self.LUT[self.state]])

    def next_graypoint(self):
        # Advance the state machine to the next graypoint.
        # Returns: True if the calibration is done, False otherwise
        _s = self.state
        _lut   = self.LUT
        _curve = self.curve
        if _s == GRAY50:
            # set dither to black / just-calibrated GRAY50
            self.dither_dark = _curve[_lut[GRAY00]]
            self.dither_light = _curve[_lut[GRAY50]]
            _curve[_lut[GRAY25]] = (self.dither_dark + self.dither_light) // 2
            self.state = GRAY25
        elif _s == GRAY25:
            # set dither to GRAY50 / white
            self.dither_dark = _curve[_lut[GRAY50]]
            self.dither_light = _curve[_lut[GRAY99]]
            _curve[_lut[GRAY75]] = (self.dither_dark + self.dither_light) // 2
            self.state = GRAY75
        elif _s == GRAY75:
            # set dither to black / just-calibrated GRAY25
            self.dither_dark = _curve[_lut[GRAY00]]
            self.dither_light = _curve[_lut[GRAY25]]
            _curve[_lut[GRAY12]] = (self.dither_dark + self.dither_light) // 2
            self.state = GRAY12
        elif _s == GRAY12:
            # set dither to just-calibrated GRAY75 / GRAY99
            self.dither_dark = _curve[_lut[GRAY75]]
            self.dither_light = _curve[_lut[GRAY99]]
            _curve[_lut[GRAY87]] = (self.dither_dark + self.dither_light) // 2
            self.state = GRAY87
        elif _s == GRAY87:
            # set dither to GRAY25 / GRAY50
            self.dither_dark = _curve[_lut[GRAY25]]
            self.dither_light = _curve[_lut[GRAY50]]
            _curve[_lut[GRAY37]] = (self.dither_dark + self.dither_light) // 2
            self.state = GRAY37
        elif _s == GRAY37:
            # set dither to GRAY50 / GRAY75
            self.dither_dark = _curve[_lut[GRAY50]]
            self.dither_light = _curve[_lut[GRAY75]]
            _curve[_lut[GRAY62]] = (self.dither_dark + self.dither_light) // 2
            self.state = GRAY62
        elif _s == GRAY62:
            # set dither back to GRAY00 / GRAY99 (start cycle over)
            self.dither_dark = _curve[_lut[GRAY00]]
            self.dither_light = _curve[_lut[GRAY99]]
            self.state = GRAY50
            # Tell caller that calibration is done
            return True
        # Default: tell caller calibration is not done yet
        return False

    def __str__(self):
        # Return printable string for this gamma curve
        return str(self.curve)


def main():
    # This function has initialization code and the main event loop. Under
    # normal circumstances, this function does not return.

    # The Feather TFT defaults to using the built-in display for a console.
    # So, first, release the default display so we can re-initialize it below.
    release_displays()
    gc.collect()

    # Initialize ST7789 display with native display size of 240x135px.
    TFT_W = const(240)
    TFT_H = const(135)
    spi = SPI()
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=TFT_W, height=TFT_H, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()

    # Make a bitmap for the gamma calibration pattern
    #
    # The calibration pattern has a thick border of a 50% dither pattern around
    # a central square of a solid color. The idea is to determine correction
    # coefficients to match perceived brightness values of the solid square
    # compared to the dithered border.
    #
    # For example, suppose the palette (pal) is
    #   pal[0] = 0x000000   # black
    #   pal[1] = 0xFFFFFF   # white
    #   pal[2] = 0x808080   # theoretically 50% gray, but likely more or less
    #
    # with a calibration pattern of
    #   010101010101
    #   101010101010
    #   010122220101
    #   101022221010
    #   010101010101
    #   101010101010
    #
    # The calibration goal would be to adjust pal[2] until it matches the
    # perceived brightness of a 50% dither between pal[0] and pal[1].

    # 1. Compute boundary coordinates for the outer dither pattern ring and
    #    the inner solid color box
    PAD    = const(32)
    LEFT   = const((TFT_W * 1) // 5)
    RIGHT  = const((TFT_W * 4) // 5)
    TOP    = const(((TFT_H - PAD) * 2 ) // 7)
    BOTTOM = const(((TFT_H - PAD) * 5 ) // 7)

    # 2. Make the bitmap
    bmp = Bitmap(TFT_W, TFT_H - PAD, 3)

    # 3. Fill bitmap with the outer dither pattern ring and inner solid box
    for y in range(bmp.height):
        for x in range(bmp.width):
            if TOP < y < BOTTOM and LEFT < x < RIGHT:
                bmp[x, y] = 2
            else:
                bmp[x, y] = (x ^ y) & 1  # 50% dither pattern between 0 and 1


    # Make a 3 color palette of black, white, and 50% gray (which will probably
    # look like something other than 50% gray because the gamma curve is wrong)
    pal = Palette(3)

    # Make a gamma correction curve manager and set the initial palette
    gamma = GammaCurve()
    gamma.update_palette3(pal)

    # Combine the bitmap and palette into a TileGrid
    test_pattern = TileGrid(bmp, pixel_shader=pal, x=0, y=PAD)

    # Make a text label for status messages
    status = bitmap_label.Label(FONT, text="", color=0xFF0000, scale=2)
    status.anchor_point = (0, 0)
    status.anchored_position = (0, 0)

    # Arrange TileGrid and label into the root group
    grp = Group(scale=1)
    grp.append(test_pattern)
    grp.append(status)
    display.root_group = grp

    # Cache frequently used callables to save time on dictionary name lookups
    # (this is a standard MicroPython performance boosting trick)
    _collect = gc.collect
    _refresh = display.refresh
    _sleep = time.sleep

    # MAIN EVENT LOOP
    error_msg = 'please enter a number from 1 to 62, or "next"'
    palette_format = 'dither:%2d/%2d box:%2d'
    print("\nBeginning gamma curve calibration...\n")
    print("- Your goal is to enter a 6-bit grayscale value (1..62) for the")
    print("  center box to make its brightness match the brightness of the")
    print("  dithered ring surrounding the box.\n")
    print("- The 3 numbers on each prompt line are gray values for the dither")
    print("  ('dither: <dark>/<light>') and the center box ('box: <box>').\n")
    print('- When the box and ring brightness match, enter "next" to advance')
    print("  to the next gray point on the calibration curve.\n\n")
    while True:
        (dark, light, mid) = [gray24_to_6(c) for c in (pal[0], pal[1], pal[2])]
        grays_status = palette_format % (dark, light, mid)
        status.text = grays_status
        _collect()
        _refresh()
        _sleep(0.1)
        # Prompt for a new grayscale value for the center box. This uses 6-bit
        # values to make the data entry easier and to use less space on the
        # TFT display's status line
        ans = input('%s  set box to: ' % grays_status)
        try:
            n = int(ans)
            if 1 <= n <= 62:
                # If answer was an in-range grayscale value, change box color
                gamma.set_gray6(n)
                gamma.update_palette3(pal)
            else:
                print(error_msg)
        except ValueError as e:
            if ans == 'next':
                # If answer was "next", advance to the next graypoint
                done = gamma.next_graypoint()
                gamma.update_palette3(pal)
                if done:
                    print("===================================")
                    print("Calibration is done!")
                    print(gamma)
                    print("===================================")
            else:
                print(error_msg)


def gray6_to_24(n):
    # Return the 6-bit grayscale argument n as a 24-bit RGB color
    if not (0 <= n <= 63):
        raise Exception(f"6-bit grayscale value out of range: {n}")
    n <<= 2
    return (n << 16) | (n << 8) | n


def gray24_to_6(c):
    # Return the 6-bit grayscale value for the 24-bit color argument c
    if not (0 <= c <= 0xffffff):
        raise Exception(f"24-bit color value out of range: {n}")
    return (c & 0xff) >> 2


main()
