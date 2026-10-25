#!/usr/bin/env python3
"""
Synthetic Benchmark Test Image Generator
Creates clearly labeled synthetic currency note test images for unit testing
and demonstration of the MATLAB Currency Note Edge Quality Inspection system.
"""

import os
import math
import random
from PIL import Image, ImageDraw, ImageFilter

def create_synthetic_dataset(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    random.seed(42)

    width = 800
    height = 500
    
    # Note dimensions
    note_w = 580
    note_h = 280
    x0 = (width - note_w) // 2
    y0 = (height - note_h) // 2
    x1 = x0 + note_w
    y1 = y0 + note_h

    # 1. Background base
    def make_base_canvas():
        img = Image.new("RGB", (width, height), (38, 42, 50))
        # Add subtle table texture
        draw = ImageDraw.Draw(img)
        for y in range(0, height, 4):
            val = random.randint(35, 45)
            draw.line([(0, y), (width, y)], fill=(val, val + 2, val + 6), width=1)
        return img

    def draw_note_body(img, note_polygon, base_color=(190, 218, 198), draw_inner_border=True):
        draw = ImageDraw.Draw(img)
        # Fill polygon
        draw.polygon(note_polygon, fill=base_color, outline=(140, 165, 145))
        
        # Draw interior decorative security patterns (simulating genuine note features)
        if draw_inner_border:
            # Inner margin rectangle
            m = 16
            inner_poly = [(x0 + m, y0 + m), (x1 - m, y0 + m), (x1 - m, y1 - m), (x0 + m, y1 - m)]
            draw.polygon(inner_poly, outline=(160, 190, 170), width=2)
            # Central watermark ellipse
            draw.ellipse([x0 + 80, y0 + 50, x0 + 200, y1 - 50], outline=(175, 205, 185), width=2)
            # Denomination box
            draw.rectangle([x1 - 180, y0 + 60, x1 - 50, y1 - 60], outline=(150, 180, 160), width=2)
            # Security thread line (dashed)
            for ty in range(y0 + 20, y1 - 20, 15):
                draw.line([(x0 + 240, ty), (x0 + 240, ty + 8)], fill=(120, 140, 130), width=3)
        return img

    # --- Test Image 1: Clean Good Note ---
    img1 = make_base_canvas()
    poly1 = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    draw_note_body(img1, poly1)
    p1 = os.path.join(output_dir, "synthetic_good_01.png")
    img1.save(p1)
    print(f"Generated: {p1}")

    # --- Test Image 2: Torn Corner (Top-Right missing triangular notch) ---
    img2 = make_base_canvas()
    notch_w = 65
    notch_h = 55
    # Build polygon with top-right corner clipped inward
    poly2 = [
        (x0, y0),
        (x1 - notch_w, y0),
        (x1 - notch_w + 10, y0 + 20),
        (x1 - 10, y0 + notch_h - 10),
        (x1, y0 + notch_h),
        (x1, y1),
        (x0, y1)
    ]
    draw_note_body(img2, poly2)
    p2 = os.path.join(output_dir, "synthetic_torn_corner_02.png")
    img2.save(p2)
    print(f"Generated: {p2}")

    # --- Test Image 3: Torn Top Edge (Irregular deep notch) ---
    img3 = make_base_canvas()
    # Top edge with irregular missing notch
    poly3 = [(x0, y0)]
    # Top edge up to notch
    poly3.append((x0 + 220, y0))
    # Notched jagged intrusion
    poly3.append((x0 + 235, y0 + 15))
    poly3.append((x0 + 250, y0 + 35))
    poly3.append((x0 + 265, y0 + 30))
    poly3.append((x0 + 280, y0 + 18))
    poly3.append((x0 + 295, y0))
    poly3.append((x1, y0))
    poly3.append((x1, y1))
    poly3.append((x0, y1))
    draw_note_body(img3, poly3)
    p3 = os.path.join(output_dir, "synthetic_torn_edge_03.png")
    img3.save(p3)
    print(f"Generated: {p3}")

    # --- Test Image 4: Folded Note (Intact edges, strong vertical crease) ---
    img4 = make_base_canvas()
    draw_note_body(img4, poly1)
    draw4 = ImageDraw.Draw(img4)
    # Draw vertical fold crease through center
    fold_x = (x0 + x1) // 2
    # Crease shadow
    draw4.line([(fold_x - 1, y0), (fold_x - 1, y1)], fill=(120, 140, 125), width=2)
    # Crease highlight
    draw4.line([(fold_x + 1, y0), (fold_x + 1, y1)], fill=(230, 245, 235), width=1)
    # Crease main dark line
    draw4.line([(fold_x, y0), (fold_x, y1)], fill=(90, 110, 95), width=2)
    p4 = os.path.join(output_dir, "synthetic_folded_04.png")
    img4.save(p4)
    print(f"Generated: {p4}")

    # --- Test Image 5: Old / Worn Note (Frayed edges, surface noise, fading) ---
    img5 = make_base_canvas()
    # Create ragged edge polygon
    poly5 = []
    # Top edge with micro variations
    for x in range(x0, x1, 10):
        dy = random.choice([-2, -1, 0, 1, 2])
        poly5.append((x, y0 + dy))
    # Right edge
    for y in range(y0, y1, 10):
        dx = random.choice([-2, -1, 0, 1, 2])
        poly5.append((x1 + dx, y))
    # Bottom edge
    for x in range(x1, x0, -10):
        dy = random.choice([-2, -1, 0, 1, 2])
        poly5.append((x, y1 + dy))
    # Left edge
    for y in range(y1, y0, -10):
        dx = random.choice([-2, -1, 0, 1, 2])
        poly5.append((x0 + dx, y))
    
    # Old faded parchment color
    draw_note_body(img5, poly5, base_color=(175, 185, 165))
    # Add surface stains and aging noise
    draw5 = ImageDraw.Draw(img5)
    for _ in range(80):
        sx = random.randint(x0 + 20, x1 - 20)
        sy = random.randint(y0 + 20, y1 - 20)
        sr = random.randint(10, 35)
        draw5.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(160, 170, 150))
    p5 = os.path.join(output_dir, "synthetic_worn_05.png")
    img5.save(p5)
    print(f"Generated: {p5}")

    # --- Test Image 6: Uniform Blank (Failure mode test) ---
    img6 = Image.new("RGB", (width, height), (50, 50, 50))
    p6 = os.path.join(output_dir, "synthetic_uniform_06.png")
    img6.save(p6)
    print(f"Generated: {p6}")

if __name__ == "__main__":
    out = "/Users/mohammedathark/Downloads/currency_note_edge_inspection/dataset/test_images"
    create_synthetic_dataset(out)
