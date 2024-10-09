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
from time import sleep

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

    # Make a text label for status messages
    status = bitmap_label.Label(FONT, text="", color=0xFF0000, scale=2)
    status.x = 0
    status.y = 8

    # Arrange TileGrid and label into the root group
    grp = Group(scale=1)
    grp.append(status)
    display.root_group = grp

    # Cache frequently used callables to save time on dictionary name lookups
    # (this is a standard MicroPython performance boosting trick)
    _collect = gc.collect
    _refresh = display.refresh
    _sleep = sleep

    # MAIN EVENT LOOP
    status.text = "Status line 01234567"
    while True:
        _collect()
        _refresh()
        _sleep(0.1)


main()
