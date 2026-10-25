# Academic Currency Note Dataset Collection Checklist & Protocol

This document outlines the protocol for populating the `dataset/` directory to satisfy the **150+ image academic requirement** for the Digital Image Processing Course Project.

---

## 1. Ethical & Legal Guidelines for Currency Note Imaging

1. **Reproduction Regulations**: Most central banks (e.g., Reserve Bank of India, Federal Reserve, European Central Bank) permit currency note photography for educational and scientific research under strict conditions:
   - Photographs must NOT be 1:1 printable counterfeiting masters.
   - Do not crop notes to print resolution without background. Capturing notes on a contrasting desktop/table with borders visible complies with fair use.
   - Images should be captured at 72–150 DPI or downsampled for computer vision inspection.
2. **Provenance & Attribution**:
   - Always record the provenance of real banknotes in `dataset/manifest.csv`.
   - Avoid downloading unverified images from social media or private stock repositories without clear licensing.

---

## 2. Target Dataset Composition (150 Images Minimum)

To establish a statistically balanced benchmark for edge inspection:

| Category | Recommended Count | Minimum Count | Visual Criteria |
| :--- | :--- | :--- | :--- |
| **Good (Intact)** | 50 images | 40 images | Fully intact boundaries, clean corners, no tears or deep folds |
| **Torn (Edge Damage)** | 50 images | 40 images | Missing corners, notched perimeter cuts, edge lacerations |
| **Folded** | 30 images | 25 images | Intact perimeter but noticeable transverse/longitudinal creases |
| **Old / Worn** | 30 images | 25 images | Frayed fibers along edges, dog-eared corners, faded ink |
| **Test Images (Synthetic)** | 6+ images | 6 images | Controlled ground-truth geometric test cases |
| **Total** | **166 images** | **150 images** | Meets and exceeds the course evaluation benchmark |

---

## 3. Recommended Open & Legitimate Dataset Repositories

Students may acquire legitimate banknotes from:

1. **Mendeley Data / Zenodo Open Datasets**:
   - Search: *"Banknote condition classification"*, *"Currency recognition dataset"*, or *"Soiled currency dataset"*.
   - Ensure the license is CC-BY 4.0 or Open Access.
2. **Central Bank Educational Specimen Archives**:
   - Official central bank security feature portals (e.g., RBI Paisa Bolta Hai, ECB Banknotes gallery).
3. **Controlled Laboratory Capture**:
   - Camera setup: Smartphone or webcam mounted 25–35 cm directly above note (top-down orthogonal angle).
   - Background: Dark, non-reflective matte cardstock (e.g., navy blue, black, or dark grey).
   - Illumination: Diffuse ambient light or dual LED side lights (prevent harsh specular glare).

---

## 4. Populating the Folders

Place captured images into their corresponding directories:
```
dataset/
├── good/         <-- Intact notes (note_good_001.jpg, ...)
├── folded/       <-- Creased notes (note_folded_001.jpg, ...)
├── torn/         <-- Notched/missing edge notes (note_torn_001.jpg, ...)
├── old_worn/     <-- Frayed/faded notes (note_worn_001.jpg, ...)
└── test_images/  <-- Synthetic benchmark references
```

After adding images, run the validation tool in MATLAB:
```matlab
validate_dataset('dataset')
```
This script will count items across all subdirectories, detect unreadable files, flag duplicate images, and verify if the 150-image benchmark has been fulfilled.
