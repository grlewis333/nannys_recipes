"""
Nanny's Recipes — OCR Pipeline
================================
Extracts text from recipe images using a dual OCR strategy:
  1. Tesseract OCR (best for typed/printed text)
  2. OpenAI GPT-4o Vision (best for handwritten text and annotations)

Requirements:
  pip install openai pytesseract pillow opencv-python

To run (using your conda environment):
  conda activate hspy1
  python ocr_pipeline.py

Note: When first run in Cowork, the OpenAI API was unreachable due to
the VM's network proxy. Tesseract ran successfully. Vision-based
transcriptions were produced via Claude's own vision capability during
the session. To re-run with GPT-4o on your Mac, just set your API key
below and run the script — the OpenAI calls should work fine outside
the VM.

Author: George Lewis
Date: 2026-02-09
"""

import os
import json
import base64
import time
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import cv2
import numpy as np
import pytesseract
from openai import OpenAI

# =============================================================================
# Configuration
# =============================================================================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_KEY_HERE")

# Paths — adjust these if running from a different location
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "Images"
OUTPUT_DIR = BASE_DIR / "ocr_output"
PREPROCESSED_DIR = OUTPUT_DIR / "preprocessed"
TESSERACT_DIR = OUTPUT_DIR / "tesseract"
GPT4O_DIR = OUTPUT_DIR / "gpt4o"
AUDIT_FILE = BASE_DIR / "image_audit.json"

# GPT-4o model to use (gpt-4o is the best for vision tasks)
GPT4O_MODEL = "gpt-4o"

# =============================================================================
# Step 1: Load the image audit
# =============================================================================
def load_audit():
    """Load the image audit JSON that maps recipes to their source images."""
    with open(AUDIT_FILE, "r") as f:
        return json.load(f)


# =============================================================================
# Step 2: Image Preprocessing (PIL + OpenCV)
# =============================================================================
def preprocess_for_tesseract(image_path: Path, output_path: Path):
    """
    Preprocess an image to improve Tesseract OCR accuracy.

    Pipeline:
      1. Load image
      2. Convert to grayscale
      3. Resize if too small
      4. Apply adaptive thresholding
      5. Denoise
      6. Save preprocessed image
    """
    # Load with OpenCV
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"  [WARN] Could not load: {image_path.name}")
        return None

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Resize if the image is small (helps Tesseract)
    h, w = gray.shape
    if max(h, w) < 1500:
        scale = 1500 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )

    # Light denoising
    denoised = cv2.fastNlMeansDenoising(thresh, h=10)

    # Save preprocessed image
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), denoised)

    return output_path


# =============================================================================
# Step 3a: Tesseract OCR
# =============================================================================
def run_tesseract(image_path: Path) -> str:
    """Run Tesseract OCR on a preprocessed image and return the raw text."""
    img = Image.open(image_path)

    # Configure Tesseract for best results on recipe text
    custom_config = r"--oem 3 --psm 6"
    text = pytesseract.image_to_string(img, config=custom_config)

    return text.strip()


# =============================================================================
# Step 3b: GPT-4o Vision OCR
# =============================================================================
def encode_image_base64(image_path: Path) -> str:
    """Encode an image file as a base64 string for the OpenAI API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def run_gpt4o_vision(client: OpenAI, image_paths: list[Path], recipe_type: str) -> str:
    """
    Send one or more images to GPT-4o Vision for transcription.

    For multi-page recipes, all pages are sent in a single request
    so the model can understand the full context.

    Args:
        client: OpenAI client instance
        image_paths: List of image file paths (one per page)
        recipe_type: 'typed', 'handwritten', or 'mixed'

    Returns:
        Transcribed text from the model
    """
    # Build the prompt based on recipe type
    type_guidance = {
        "typed": "This is a typewritten recipe, possibly with handwritten annotations in pen/pencil alongside the typed text.",
        "handwritten": "This is a fully handwritten recipe in pen/pencil.",
        "mixed": "This recipe has both typed/printed text and handwritten annotations overlaid on top."
    }

    page_note = ""
    if len(image_paths) > 1:
        page_note = f"\n\nThis recipe spans {len(image_paths)} pages/images. Please transcribe all pages in order as one continuous recipe."

    prompt = f"""You are a careful transcription assistant helping to preserve a grandmother's handwritten curry recipe collection.

{type_guidance.get(recipe_type, type_guidance['handwritten'])}
{page_note}

Please transcribe the recipe EXACTLY as written, preserving:
- The recipe title
- All ingredients with their quantities and units
- All method/cooking instructions
- Any handwritten annotations or notes (mark these clearly as [Handwritten note: ...])
- Any corrections or alternative quantities written alongside

Important details:
- "Zeera" = cumin, "Haldi" = turmeric, "Dhania" = coriander — keep the original terms
- Preserve fractions (½, ¼, etc.) as written
- If text is unclear, use [unclear: best guess]
- Maintain the original structure (title, ingredients list, method)
- Do NOT add any interpretation or modernisation — transcribe faithfully

Output the transcription as plain text, preserving the recipe's natural structure."""

    # Build the message content with image(s)
    content = [{"type": "text", "text": prompt}]

    for i, img_path in enumerate(image_paths):
        b64 = encode_image_base64(img_path)
        suffix = img_path.suffix.lower()
        media_type = "image/jpeg" if suffix in [".jpg", ".jpeg"] else "image/png"

        if len(image_paths) > 1:
            content.append({"type": "text", "text": f"\n--- Page {i+1} of {len(image_paths)} ---"})

        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{b64}",
                "detail": "high"
            }
        })

    # Call the API
    response = client.chat.completions.create(
        model=GPT4O_MODEL,
        messages=[{"role": "user", "content": content}],
        max_tokens=4096,
        temperature=0.1  # Low temperature for faithful transcription
    )

    return response.choices[0].message.content.strip()


# =============================================================================
# Step 4: Run the full pipeline
# =============================================================================
def run_pipeline():
    """Execute the complete OCR pipeline."""

    print("=" * 60)
    print("Nanny's Recipes — OCR Pipeline")
    print("=" * 60)

    # Create output directories
    for d in [OUTPUT_DIR, PREPROCESSED_DIR, TESSERACT_DIR, GPT4O_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Load audit
    audit = load_audit()
    recipes = audit["recipes"]
    print(f"\nFound {len(recipes)} unique recipes to process.\n")

    # Initialise OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Results storage
    all_results = []

    for i, recipe in enumerate(recipes):
        recipe_id = recipe["id"]
        title = recipe["title"]
        rtype = recipe["type"]
        best_images = recipe["best_images"]

        print(f"\n[{i+1}/{len(recipes)}] Processing: {title}")
        print(f"  Type: {rtype}")
        print(f"  Images: {best_images}")

        result = {
            "id": recipe_id,
            "title": title,
            "type": rtype,
            "source_images": best_images,
            "tesseract_raw": "",
            "gpt4o_raw": "",
            "notes": recipe.get("notes", "")
        }

        # --- Tesseract OCR ---
        tesseract_texts = []
        for img_name in best_images:
            img_path = IMAGES_DIR / img_name
            if not img_path.exists():
                print(f"  [WARN] Image not found: {img_name}")
                continue

            # Preprocess
            preproc_path = PREPROCESSED_DIR / f"{recipe_id}_{img_name}"
            preprocess_for_tesseract(img_path, preproc_path)

            if preproc_path.exists():
                tess_text = run_tesseract(preproc_path)
                tesseract_texts.append(tess_text)
                print(f"  Tesseract: {len(tess_text)} chars extracted")

        result["tesseract_raw"] = "\n\n--- PAGE BREAK ---\n\n".join(tesseract_texts)

        # Save Tesseract output
        tess_file = TESSERACT_DIR / f"{recipe_id}.txt"
        with open(tess_file, "w") as f:
            f.write(result["tesseract_raw"])

        # --- GPT-4o Vision OCR ---
        image_paths = [IMAGES_DIR / name for name in best_images if (IMAGES_DIR / name).exists()]

        if image_paths:
            try:
                gpt4o_text = run_gpt4o_vision(client, image_paths, rtype)
                result["gpt4o_raw"] = gpt4o_text
                print(f"  GPT-4o:    {len(gpt4o_text)} chars extracted")

                # Save GPT-4o output
                gpt4o_file = GPT4O_DIR / f"{recipe_id}.txt"
                with open(gpt4o_file, "w") as f:
                    f.write(gpt4o_text)

                # Rate limiting — be kind to the API
                time.sleep(1)

            except Exception as e:
                print(f"  [ERROR] GPT-4o failed: {e}")
                result["gpt4o_raw"] = f"ERROR: {e}"

        all_results.append(result)

    # Save combined results
    results_file = OUTPUT_DIR / "ocr_results_combined.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete!")
    print(f"  Results saved to: {results_file}")
    print(f"  Tesseract outputs: {TESSERACT_DIR}")
    print(f"  GPT-4o outputs:    {GPT4O_DIR}")
    print(f"{'=' * 60}")

    return all_results


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    results = run_pipeline()
