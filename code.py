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
    #
    PAD    = const(24)
    LEFT   = const((TFT_W * 1) // 5)
    RIGHT  = const((TFT_W * 4) // 5)
    TOP    = const(((TFT_H - PAD) * 2 ) // 7)
    BOTTOM = const(((TFT_H - PAD) * 5 ) // 7)

    bmp = Bitmap(TFT_W, TFT_H - PAD, 3)
    for y in range(bmp.height):
        for x in range(bmp.width):
            if TOP < y < BOTTOM and LEFT < x < RIGHT:
                bmp[x, y] = 2
            else:
                bmp[x, y] = (x ^ y) & 1  # 50% dither pattern between 0 and 1

    # Make a 3 color palette
    pal = Palette(3)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF
    pal[2] = 0x808080

    # Combine the bitmap and palette into a TileGrid
    test_pattern = TileGrid(bmp, pixel_shader=pal, x=0, y=PAD)

    # Make a text label for status messages
    status = bitmap_label.Label(FONT, text="", color=0xFF0000, scale=2)
    status.anchor_point = (0, 0)
    status.anchored_position = (0, 0)
    status.text = f"{pal[0]:06x} {pal[1]:06x} {pal[2]:06x}"

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
    while True:
        _collect()
        _refresh()
        _sleep(0.1)


main()
