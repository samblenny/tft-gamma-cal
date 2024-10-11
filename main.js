// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
//
"use strict";

const CANVAS = document.querySelector('#canvas');
const CTX = CANVAS.getContext("2d", {willReadFrequently: true});

const GRAY03 = document.querySelector('#gray03');
const GRAY06 = document.querySelector('#gray06');
const GRAY12 = document.querySelector('#gray12');
const GRAY25 = document.querySelector('#gray25');
const GRAY37 = document.querySelector('#gray37');
const GRAY50 = document.querySelector('#gray50');
const GRAY62 = document.querySelector('#gray62');
const GRAY75 = document.querySelector('#gray75');
const GRAY87 = document.querySelector('#gray87');

const STATUS = document.querySelector('#status');

function paintTestPattern() {
    const w = 200;
    const h = 300;
    CANVAS.width = w;
    CANVAS.height = h;
    // getImageData returns RGBA Uint8ClampedArray of pixels in row-major order
    const imageData = CTX.getImageData(0, 0, w, h);
    const rgba = imageData.data;
    const gray06 = GRAY06.value;
    const gray03 = GRAY03.value;
    const gray12 = GRAY12.value;
    const gray25 = GRAY25.value;
    const gray37 = GRAY37.value;
    const gray50 = GRAY50.value;
    const gray62 = GRAY62.value;
    const gray75 = GRAY75.value;
    const gray87 = GRAY87.value;
    let curve = [gray03, gray06, gray12, gray25, gray37, gray50, gray62, gray75, gray87];
    STATUS.textContent = "curve: " + curve.join(" ");
    let dither_dark = 0;
    let dither_light = 255;
    let solid = 127;
    for (let y=0; y<h; y++) {
        let rowBase = y * w * 4;
        if (y < h * (1/9)) {
            dither_dark = 0;
            solid = gray03;
            dither_light = gray06;
        } else if (y < h * (2/9)) {
            dither_dark = 0;
            solid = gray06;
            dither_light = gray12;
        } else if (y < h * (3/9)) {
            dither_dark = 0;
            solid = gray12;
            dither_light = gray25;
        } else if (y < h * (4/9)) {
            dither_dark = 0;
            solid = gray25;
            dither_light = gray50;
        } else if (y < h * (5/9)) {
            dither_dark = gray25;
            solid = gray37;
            dither_light = gray50;
        } else if (y < h * (6/9)) {
            dither_dark = 0;
            solid = gray50;
            dither_light = 255;
        } else if (y < h * (7/9)) {
            dither_dark = gray50;
            solid = gray62;
            dither_light = gray75;
        } else if (y < h * (8/9)) {
            dither_dark = gray50;
            solid = gray75;
            dither_light = 255;
        } else {
            dither_dark = gray75;
            solid = gray87;
            dither_light = 255;
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

function handleSlider(tag, event) {
    paintTestPattern();
}

GRAY03.addEventListener("input", (e) => { handleSlider("GRAY03", e); });
GRAY06.addEventListener("input", (e) => { handleSlider("GRAY06", e); });
GRAY12.addEventListener("input", (e) => { handleSlider("GRAY12", e); });
GRAY25.addEventListener("input", (e) => { handleSlider("GRAY25", e); });
GRAY37.addEventListener("input", (e) => { handleSlider("GRAY37", e); });
GRAY50.addEventListener("input", (e) => { handleSlider("GRAY50", e); });
GRAY62.addEventListener("input", (e) => { handleSlider("GRAY62", e); });
GRAY75.addEventListener("input", (e) => { handleSlider("GRAY75", e); });
GRAY87.addEventListener("input", (e) => { handleSlider("GRAY87", e); });

paintTestPattern();
