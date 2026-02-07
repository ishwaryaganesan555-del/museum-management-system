"""
Doodle / cartoonize an input image and save the result.

Usage:
    python tools/doodle_from_image.py --in path/to/input.jpg --out path/to/output.png --k 8

Dependencies:
    pip install opencv-python pillow numpy

This script uses bilateral filtering, median blur, adaptive thresholding
and k-means color quantization to produce a doodle-like output.
"""

import argparse
import cv2
import numpy as np
from PIL import Image


def color_quantize(image, k=8):
    data = np.float32(image).reshape((-1, 3))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    result = centers[labels.flatten()].reshape(image.shape)
    return result


def doodleify(img_bgr, k=8):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Smooth colors but keep edges
    color = cv2.bilateralFilter(img_rgb, d=9, sigmaColor=75, sigmaSpace=75)

    # Quantize colors to get flat regions (cartoon/doodle look)
    quant = color_quantize(color, k=k)

    # Prepare edge mask
    gray = cv2.cvtColor(color, cv2.COLOR_RGB2GRAY)
    blur = cv2.medianBlur(gray, 7)
    edges = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                  cv2.THRESH_BINARY, blockSize=9, C=2)

    # Invert edges so lines become black (0)
    edges_inv = cv2.bitwise_not(edges)
    edges_inv_rgb = cv2.cvtColor(edges_inv, cv2.COLOR_GRAY2RGB)

    # Combine quantized color with edge mask
    doodle = cv2.bitwise_and(quant, edges_inv_rgb)

    return doodle


def main():
    parser = argparse.ArgumentParser(description="Make a doodle/cartoon from an image")
    parser.add_argument("--in", "-i", dest="infile", required=True, help="Input image path")
    parser.add_argument("--out", "-o", dest="outfile", required=True, help="Output image path")
    parser.add_argument("--k", "-k", dest="k", type=int, default=8, help="Number of color clusters (lower = flatter)")

    args = parser.parse_args()

    img = cv2.imread(args.infile)
    if img is None:
        print(f"ERROR: Could not read input file: {args.infile}")
        return

    doodle = doodleify(img, k=args.k)

    # Save with PIL to ensure correct color ordering
    out_img = Image.fromarray(doodle)
    out_img.save(args.outfile)
    print(f"Saved doodle image to {args.outfile}")


if __name__ == '__main__':
    main()
