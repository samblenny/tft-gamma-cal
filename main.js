// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
//
"use strict";

const CANVAS = document.querySelector('#canvas');
const CTX = CANVAS.getContext("2d", {willReadFrequently: true});

const GRAY1_2   = document.querySelector('#gray1_2');
const GRAY1_4   = document.querySelector('#gray1_4');
const GRAY1_8   = document.querySelector('#gray1_8');
const GRAY1_16  = document.querySelector('#gray1_16');
const GRAY1_32  = document.querySelector('#gray1_32');
const GRAY1_64  = document.querySelector('#gray1_64');
const GRAY1_128 = document.querySelector('#gray1_128');

const STATUS = document.querySelector('#status');

function paintTestPattern() {
    const w = 134;
    const h = 240;
    CANVAS.width = w;
    CANVAS.height = h;
    // getImageData returns RGBA Uint8ClampedArray of pixels in row-major order
    const imageData = CTX.getImageData(0, 0, w, h);
    const rgba = imageData.data;
    const gray1_2  = GRAY1_2.value;
    const gray1_4  = GRAY1_4.value;
    const gray1_8  = GRAY1_8.value;
    const gray1_16 = GRAY1_16.value;
    const gray1_32 = GRAY1_32.value;
    const gray1_64 = GRAY1_64.value;
    const gray1_128 = GRAY1_128.value;
    let curve = [gray1_2, gray1_4, gray1_8, gray1_16, gray1_32, gray1_64, gray1_128];
    STATUS.textContent = "curve: " + curve.join(" ");
    let dither_dark = 0;
    let dither_light = 255;
    let solid = 127;
    for (let y=0; y<h; y++) {
        let rowBase = y * w * 4;
        if (y < h * (1/7)) {
            solid = gray1_2;
            dither_light = 255;
        } else if (y < h * (2/7)) {
            solid = gray1_4;
            dither_light = gray1_2;
        } else if (y < h * (3/7)) {
            solid = gray1_8;
            dither_light = gray1_4;
        } else if (y < h * (4/7)) {
            solid = gray1_16;
            dither_light = gray1_8;
        } else if (y < h * (5/7)) {
            solid = gray1_32;
            dither_light = gray1_16;
        } else if (y < h * (6/7)) {
            solid = gray1_64;
            dither_light = gray1_32;
        } else {
            solid = gray1_128;
            dither_light = gray1_64;
        }
        for(let x=0; x<w; x++) {
            let dither = (x ^ y) & 1;
            let luma = dither ? dither_dark : dither_light;
            if ((w/3 < x) && (x < w*(2/3))) {
                luma = solid;
            }
            let i = rowBase + (x * 4);
            rgba[i + 0] = luma;
            rgba[i + 1] = luma;
            rgba[i + 2] = luma;
            rgba[i + 3] = 255;
        }
    }
    CTX.putImageData(imageData, 0, 0);
}

GRAY1_2.addEventListener("input", paintTestPattern);
GRAY1_4.addEventListener("input", paintTestPattern);
GRAY1_8.addEventListener("input", paintTestPattern);
GRAY1_16.addEventListener("input", paintTestPattern);
GRAY1_32.addEventListener("input", paintTestPattern);
GRAY1_64.addEventListener("input", paintTestPattern);
GRAY1_128.addEventListener("input", paintTestPattern);

paintTestPattern();
