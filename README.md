# Currency Note Edge Quality Inspection

An academic Digital Image Processing (DIP) project that inspects, segments, and measures physical edge damage (tears, missing corners, edge notches, folding, and wear) on Indian currency banknotes.

The project features a **native Python image-processing pipeline**, a **FastAPI backend**, an **interactive web dashboard**, and includes **2,000 verified images** from the Mendeley Spoilt Indian Banknotes dataset. All 15 original MATLAB `.m` algorithm files are retained in the project root for academic review.

---

## 1. Project Overview & Workflow

```
┌─────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│  Input Image    │ ──> │   Pre-Processing     │ ──> │ Multi-Cue Segmentation │
│ (Real/Synthetic)│     │ Aspect-Ratio Scaling │     │   CIE Lab Color Space  │
└─────────────────┘     └──────────────────────┘     └────────────────────────┘
                                                                  │
                                                                  ▼
┌─────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│ Results Export  │ <── │ 4-Edge Defect Meas.  │ <── │ Nominal Envelope &     │
│ (PNG, JSON, CSV)│     │ Projected Linear Span│     │ 4-Corner Cyclic Order  │
└─────────────────┘     └──────────────────────┘     └────────────────────────┘
```

1. **Pre-Processing (`image_processing/preprocess.py`)**: Validates input format (RGB/grayscale array or file), normalizes dimensions preserving aspect ratio, and prepares denoised grayscale and color channels.
2. **Boundary Detection (`image_processing/boundary.py`)**: Uses CIE Lab border color sampling and shadow-immune chromaticity distance ($\Delta C = \sqrt{\Delta a^2 + \Delta b^2}$) to segment notes cleanly even on colored mats under non-uniform illumination. Rotated note corners are sorted cyclically clockwise to prevent crossed diagonals.
3. **Independent 4-Edge Defect Analysis (`image_processing/edges.py`)**: Evaluates Top, Right, Bottom, and Left edges independently. Defect runs are projected onto the nominal edge line segment, with overlapping defect intervals merged in 1D parameter space.
4. **Damage Calculation (`image_processing/damage.py`)**: Computes total edge damage percentage as:
   $$\text{Edge Damage \%} = \frac{\sum L_{\text{damaged}}}{\text{Nominal Perimeter}} \times 100$$
   Guarantees that total damaged length never exceeds total nominal perimeter.
5. **Classification (`image_processing/classify.py`)**: Classifies banknotes into **Good**, **Torn**, **Folded**, **Old/Worn**, or **Needs Manual Inspection** when boundary extraction confidence is low.
6. **Visualization (`image_processing/visualize.py`)**: Generates 4-panel quad comparisons with defect overlays strictly masked to the banknote envelope, ensuring background pixels are never marked as damage.

---

## 2. Architecture & Role of Implementation Files

| Layer | Implementation | Purpose |
| :--- | :--- | :--- |
| **Live Web App & API** | `Python 3` + `FastAPI` + `Uvicorn` | Serves dashboard, handles uploads, streams dataset images, and executes batch evaluations. |
| **Live Image Processing**| `image_processing/` (`NumPy`, `SciPy`, `scikit-image`, `Pillow`)| Executes all 8 image-processing steps natively in Python without requiring OpenCV, MATLAB, or Octave runtimes. |
| **Academic Deliverables**| Root `.m` files (`process_currency_note.m`, etc.) | Retained for academic review, grading, and execution in compatible MATLAB environments. |
| **Interactive Dashboard**| `static/` (`HTML5`, `Vanilla CSS`, `Vanilla JS`) | Provides real-time interactive inspection, dataset browsing, and batch evaluation. |

> [!NOTE]
> The live application runs 100% in Python. You do **NOT** need MATLAB, GNU Octave, or OpenCV installed to run the web application.

---

## 3. Dataset Integration

- **Source**: *Dataset of Spoilt Banknotes of India (Rupees)* — [Mendeley Data v4](https://data.mendeley.com/datasets/jh6979fg2t/4)
- **Packaged Selection**: Exactly **2,000 unique, readable banknote images** are packaged inside `dataset/`, organized into 8 balanced categories (250 images each):
  - `Spoilt New Indian Bank Notes/New 10 Rupees` (250 images)
  - `Spoilt New Indian Bank Notes/New 20 Rupees` (250 images)
  - `Spoilt New Indian Bank Notes/New 50 Rupees` (250 images)
  - `Spoilt New Indian Bank Notes/New 100 Rupees` (250 images)
  - `Spoilt Old Indian Bank Notes/Old 10 Rupees` (250 images)
  - `Spoilt Old Indian Bank Notes/Old 20 Rupees` (250 images)
  - `Spoilt Old Indian Bank Notes/Old 50 Rupees` (250 images)
  - `Spoilt Old Indian Bank Notes/Old 100 Rupees` (250 images)
- **Manifest**: `dataset/selected_2000_manifest.csv` indexes every image with its SHA-256 hash, dimensions, and relative path.
- **Portability**: All dataset paths resolve relative to the project directory. No hardcoded or machine-specific paths exist.

---

## 4. System Requirements

- **Operating System**: macOS, Linux, or Windows (WSL recommended on Windows).
- **Python**: Python 3.9, 3.10, 3.11, or 3.12.
- **Hardware**: Any modern standard computer (2 GB RAM minimum, 500 MB free disk space).

---

## 5. Quick-Start Guide

### Option A: One-Command Startup (macOS / Linux)

Open a terminal, navigate into the project directory, and run:

```bash
cd currency_note_edge_inspection
./launch.sh
```

`launch.sh` automatically:
1. Detects Python 3 on your PATH.
2. Creates and activates a local `.venv` virtual environment if not already present.
3. Installs or verifies dependencies from `requirements.txt`.
4. Creates required output directories (`results/`, `uploads/`).
5. Verifies the dataset and manifest.
6. Starts the Uvicorn web server at **http://127.0.0.1:8000**.

---

### Option B: Manual Setup (macOS / Linux / Windows)

#### 1. Navigate to the project directory
```bash
cd currency_note_edge_inspection
```

#### 2. Create and activate a virtual environment
- **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- **Windows (Command Prompt / PowerShell)**:
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate
  ```

#### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Start the web application
```bash
python3 -m uvicorn server:app --host 127.0.0.1 --port 8000
```
On Windows, use:
```cmd
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

#### 5. Open in browser
Open **http://127.0.0.1:8000** in Google Chrome, Firefox, Safari, or Microsoft Edge.

---

### Option C: Running from VS Code

1. Launch VS Code and open the `currency_note_edge_inspection` folder (`File` → `Open Folder...`).
2. Open the integrated terminal (`Terminal` → `New Terminal` or `` Ctrl+` `` / `` Cmd+` ``).
3. Run:
   ```bash
   ./launch.sh
   ```
4. Click on the printed local URL [http://127.0.0.1:8000](http://127.0.0.1:8000) or open it in your browser.

---

## 6. How to Use the Dashboard

1. **Quick Samples**: Click any of the preloaded synthetic benchmark samples in the sidebar (**Clean Note**, **Torn Corner**, **Torn Edge**, **Folded Crease**, **Worn Frayed**, or **Blank Canvas**).
2. **Upload Custom Note**: Drag and drop any banknote photo or click the file uploader to test your own images.
3. **Dataset Browser**: Switch to the **Mendeley Dataset Browser** tab:
   - Filter by denomination (e.g., `New 10 Rupees`, `Old 100 Rupees`).
   - Page through the 2,000 real banknote thumbnails.
   - Click **Analyze** on any thumbnail to run full edge defect inspection.
4. **Interactive 2x2 Inspection Panels**:
   - **Original**: Normalized input image.
   - **Preprocessed Grayscale**: Denoised and contrast-enhanced channel.
   - **Boundary & Corners**: Nominal bounding rectangle and cyclic corner markers.
   - **Damage Overlay**: Red overlay highlighting defect pockets and damaged edge segments.
5. **Metrics & Export**:
   - Inspect individual Top, Right, Bottom, and Left edge damage percentages and depths.
   - Click **Download JSON Report** for full numeric metadata.
   - Click **Download Quad Composite** for the 2x2 summary image.
6. **Batch Evaluation**:
   - Switch to the **Batch Evaluation** tab.
   - Select a sample count (e.g., 20 or 50 images) and click **Start Batch Evaluation**.
   - Download the generated `batch_evaluation_summary.csv` containing metrics across all evaluated notes.

---

## 7. Verification & Automated Tests

To run the complete automated test suite (15 unit and regression tests):

```bash
python3 -m unittest tests/test_suite.py
```

### Test Suite Coverage

```text
test_01_rgb_and_grayscale_inputs ............................ ok
test_02_invalid_image_handling .............................. ok
test_03_blank_uniform_image ................................. ok
test_04_synthetic_clean_note ................................ ok
test_05_synthetic_torn_notes ................................ ok
test_06_damage_percentage_calculation ....................... ok
test_07_classification_uncertainty .......................... ok
test_08_manifest_uniqueness ................................. ok
test_09_exact_2000_selection_requirement .................... ok
test_10_actual_dataset_image_analysis ....................... ok
test_11_exported_artifacts .................................. ok
test_12_api_endpoints ....................................... ok
test_13_regression_10_new_12_banknote ....................... ok
test_14_geometric_consistency_and_perimeter_bound ........... ok
test_15_visualization_masking_integrity ..................... ok

----------------------------------------------------------------------
Ran 15 tests in 21.690s

OK
```

### Health Check Endpoint

Verify the running API from terminal:

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "engine": "Python 3 Digital Image Processing (Native)",
  "selected_images_count": 2000,
  "octave_runtime_required": false,
  "matlab_runtime_required": false,
  "opencv_used": false
}
```

---

## 8. Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `Address already in use: 8000` | Another process is using port 8000. | `launch.sh` automatically terminates dangling instances on port 8000. Or run `lsof -ti :8000 \| xargs kill -9`. |
| `python3: command not found` | Python is not installed or not on PATH. | Install Python 3.9+ from [python.org](https://www.python.org/) and check `Add Python to PATH`. |
| `Permission denied: ./launch.sh` | Shell script lacks execution bit. | Run `chmod +x launch.sh`. |
| `Failed to load image` | Unreadable format or missing path. | Ensure image is in JPG, PNG, or BMP format. |
| `Boundary extraction failed` | Low-contrast or blank uniform image. | The pipeline safely classifies this as **Needs Manual Inspection** rather than reporting false damage. |

---

## 9. Academic & Legal Disclaimer

This software is developed strictly for **academic educational coursework and Digital Image Processing algorithm research**.
- It does **NOT** verify legal tender authenticity, check watermarks under UV light, or inspect microprinting or anti-counterfeit features.
- All edge damage percentages and condition categories are heuristic 2D image processing estimates.
