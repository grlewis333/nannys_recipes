"""
Build the static HTML file for Nanny's Recipes.

Reads recipes.json and the original images, then produces a single
self-contained HTML file with:
  - Embedded base64 images (recipe originals + banner family photos)
  - Recipe cards with photos shown by default, tap-to-enlarge lightbox
  - Search/filter functionality
  - Responsive design (mobile-friendly)
  - Print-friendly CSS
  - Warm, family-friendly colour scheme

HOW TO MODIFY AND RECOMPILE:
  1. Edit recipes.json to fix any transcription text
     (each recipe has: title, ingredients, method, notes)
  2. Run: python build_html.py
  3. Open nannys_recipes.html in a browser to check
  4. Share the HTML file — it's fully self-contained

Usage:
  python build_html.py
"""

import json
import base64
from pathlib import Path
import sys

# =============================================================================
# Configuration — adjust these paths if running from a different location
# =============================================================================
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "Images"
BANNER_DIR = BASE_DIR / "banner_photos"
RECIPES_FILE = BASE_DIR / "recipes.json"
OUTPUT_FILE = BASE_DIR / "nannys_recipes.html"

# Recipe display order — first recipe appears at the top
# Edit this list to reorder. Use recipe IDs from recipes.json.
RECIPE_ORDER = [
    "green_masala_bryani",           # Everyone's favourite!
    "chicken_curry_handwritten",
    "chicken_curry_typed",
    "ball_curry",
    "fish_curry",
    "coconut_fish_prawn_curry",
    "prawn_balchow",
    "pepper_water_typed",
    "pepper_water_handwritten",
    "breast_pepper_water",
    "aubergine_brinjal_fry",
    "brinjal_ladies_fingers",
    "mixed_frozen_veg",
    "dosais",
    "johns_green_masala_curry",
    "johns_3_bean_curry",
]


def encode_image(image_path: Path) -> str:
    """Encode an image as a base64 data URI."""
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in [".jpg", ".jpeg"] else "image/png"
    return f"data:{mime};base64,{data}"


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "<br>"))


def build_recipe_card(recipe: dict, image_data: dict) -> str:
    """Build the HTML for a single recipe card."""
    recipe_id = recipe["id"]
    title = recipe["title"]
    rtype = recipe["type"]
    ingredients = recipe.get("ingredients", [])
    method = recipe.get("method", "")
    notes = recipe.get("notes", "")
    source_images = recipe.get("source_images", [])

    # Type badge
    type_class = {"typed": "badge-typed", "handwritten": "badge-handwritten", "mixed": "badge-mixed"}
    badge = f'<span class="badge {type_class.get(rtype, "badge-mixed")}">{rtype}</span>'

    # Ingredients HTML
    ingredients_html = ""
    for ing in ingredients:
        if ing.startswith("---") and ing.endswith("---"):
            section_title = ing.strip("- ")
            ingredients_html += f'<li class="ingredient-section">{section_title}</li>'
        elif ing == "":
            continue
        elif ing.startswith("Then add:") or ing.startswith("Then add"):
            ingredients_html += f'<li class="ingredient-instruction">{escape_html(ing)}</li>'
        else:
            ing_html = escape_html(ing)
            ing_html = ing_html.replace("[Handwritten:", '<span class="handwritten-note">[Handwritten:')
            ing_html = ing_html.replace("[Handwritten note:", '<span class="handwritten-note">[Note:')
            if '<span class="handwritten-note">' in ing_html:
                ing_html = ing_html.replace("]", ']</span>', ing_html.count('<span'))
            ingredients_html += f"<li>{ing_html}</li>"

    # Method HTML
    method_html = ""
    if method:
        method_paras = method.split("\n\n")
        for para in method_paras:
            para = para.strip()
            if para.startswith("---") and para.endswith("---"):
                section_title = para.strip("- ")
                method_html += f'<h4 class="method-subsection">{escape_html(section_title)}</h4>'
            elif para.startswith("- "):
                items = para.split("\n")
                method_html += "<ul class='method-list'>"
                for item in items:
                    method_html += f"<li>{escape_html(item.lstrip('- '))}</li>"
                method_html += "</ul>"
            elif para:
                para_html = escape_html(para)
                para_html = para_html.replace("[Handwritten:", '<span class="handwritten-note">[Handwritten:')
                if '<span class="handwritten-note">' in para_html:
                    para_html = para_html.replace("]", ']</span>', para_html.count('<span'))
                method_html += f"<p>{para_html}</p>"

    # Notes HTML
    notes_html = ""
    if notes:
        notes_html = f'<div class="recipe-notes"><strong>Notes:</strong> {escape_html(notes)}</div>'

    # Image gallery — shown by default, clickable to enlarge
    images_html = ""
    for img_name in source_images:
        img_path = IMAGES_DIR / img_name
        if img_path.exists() and img_name in image_data:
            images_html += f'''
            <div class="original-photo" onclick="openLightbox(this.querySelector('img').src)">
                <img src="{image_data[img_name]}" alt="Original: {escape_html(title)}" loading="lazy">
                <span class="photo-caption">Tap to enlarge</span>
            </div>'''

    card_html = f'''
    <article class="recipe-card" data-title="{escape_html(title.lower())}" data-type="{rtype}" id="{recipe_id}">
        <div class="card-header">
            <h2>{escape_html(title)}</h2>
            {badge}
        </div>

        <div class="card-content">
            <div class="card-text">
                <div class="ingredients-section">
                    <h3>Ingredients</h3>
                    <ul class="ingredients-list">
                        {ingredients_html}
                    </ul>
                </div>

                {"<div class='method-section'><h3>Method</h3>" + method_html + "</div>" if method_html else ""}

                {notes_html}
            </div>

            <div class="card-photos">
                {images_html if images_html else '<p class="no-photo">No original photo available</p>'}
            </div>
        </div>
    </article>'''

    return card_html


def build_html():
    """Build the complete HTML file."""
    print("Loading recipes...")
    with open(RECIPES_FILE, "r") as f:
        recipes = json.load(f)

    # Reorder recipes according to RECIPE_ORDER
    recipe_map = {r["id"]: r for r in recipes}
    ordered_recipes = []
    for rid in RECIPE_ORDER:
        if rid in recipe_map:
            ordered_recipes.append(recipe_map[rid])
        else:
            print(f"  [WARN] Recipe ID '{rid}' in RECIPE_ORDER not found in recipes.json")
    # Add any recipes not in RECIPE_ORDER at the end
    ordered_ids = set(RECIPE_ORDER)
    for r in recipes:
        if r["id"] not in ordered_ids:
            ordered_recipes.append(r)
            print(f"  [INFO] Recipe '{r['id']}' not in RECIPE_ORDER, appended at end")

    recipes = ordered_recipes
    print(f"Found {len(recipes)} recipes.")

    # Pre-encode recipe images
    print("Encoding recipe images...")
    image_data = {}
    all_image_names = set()
    for recipe in recipes:
        for img_name in recipe.get("source_images", []):
            all_image_names.add(img_name)

    for img_name in sorted(all_image_names):
        img_path = IMAGES_DIR / img_name
        if img_path.exists():
            image_data[img_name] = encode_image(img_path)
            print(f"  Encoded: {img_name} ({img_path.stat().st_size // 1024}KB)")

    # Encode banner photos (if they exist)
    banner_images = []
    if BANNER_DIR.exists():
        print("Encoding banner photos...")
        for img_path in sorted(BANNER_DIR.iterdir()):
            if img_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                banner_images.append(encode_image(img_path))
                print(f"  Banner: {img_path.name} ({img_path.stat().st_size // 1024}KB)")
    else:
        print(f"  [INFO] No banner_photos/ folder found at {BANNER_DIR}")
        print(f"         Create it and add family photos, then re-run this script.")

    # Build banner photos HTML
    banner_html = ""
    if banner_images:
        banner_html = '<div class="banner-photos">'
        for i, b64 in enumerate(banner_images):
            banner_html += f'<div class="banner-photo"><img src="{b64}" alt="Family photo {i+1}"></div>'
        banner_html += '</div>'

    # Build recipe cards
    print("Building recipe cards...")
    cards_html = ""
    for recipe in recipes:
        cards_html += build_recipe_card(recipe, image_data)

    # Build nav links (used in both sidebar and mobile dropdown)
    nav_html = ""
    mobile_nav_html = ""
    for recipe in recipes:
        nav_html += f'<a href="#{recipe["id"]}" class="nav-link" data-type="{recipe["type"]}">{escape_html(recipe["title"])}</a>'
        mobile_nav_html += f'<a href="javascript:void(0)" class="mobile-nav-link" onclick="scrollToRecipe(\'{recipe["id"]}\')">{escape_html(recipe["title"])}</a>'

    # Assemble the full HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nanny's Recipes</title>
    <style>
        /* ===== CSS Reset & Base ===== */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --warm-bg: #faf6f1;
            --card-bg: #ffffff;
            --accent: #c2703e;
            --accent-dark: #9e5a30;
            --accent-light: #f0d9c4;
            --text: #3d2e1f;
            --text-light: #7a6a5a;
            --border: #e8ddd0;
            --typed-badge: #5a8f5a;
            --handwritten-badge: #8f5a5a;
            --mixed-badge: #5a5a8f;
            --shadow: 0 2px 8px rgba(61, 46, 31, 0.08);
            --shadow-hover: 0 4px 16px rgba(61, 46, 31, 0.12);
            --controls-height: 52px;
        }}

        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            background-color: var(--warm-bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* ===== Header ===== */
        .site-header {{
            background: linear-gradient(135deg, #c2703e 0%, #9e5a30 100%);
            color: white;
            padding: 2.5rem 1.5rem 1.5rem;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}

        .site-header::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E") repeat;
        }}

        .site-header h1 {{
            font-size: 2.4rem;
            font-weight: normal;
            letter-spacing: 0.05em;
            position: relative;
            z-index: 1;
        }}

        .site-header .subtitle {{
            font-size: 0.95rem;
            opacity: 0.85;
            margin-top: 0.4rem;
            font-style: italic;
            position: relative;
            z-index: 1;
        }}

        /* ===== Banner Photos ===== */
        .banner-photos {{
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-top: 1.5rem;
            position: relative;
            z-index: 1;
            flex-wrap: wrap;
        }}

        .banner-photo {{
            width: 140px;
            height: 140px;
            border-radius: 12px;
            overflow: hidden;
            border: 3px solid rgba(255,255,255,0.6);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            flex-shrink: 0;
        }}

        .banner-photo img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        /* ===== Controls (sticky search/filter bar) ===== */
        .controls {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 0.8rem 1.5rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.8rem;
            align-items: center;
            position: sticky;
            top: 0;
            background: var(--warm-bg);
            z-index: 100;
            border-bottom: 1px solid var(--border);
        }}

        .search-box {{
            flex: 1;
            min-width: 200px;
            padding: 0.5rem 1rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.95rem;
            background: var(--card-bg);
            color: var(--text);
            transition: border-color 0.2s;
        }}

        .search-box:focus {{
            outline: none;
            border-color: var(--accent);
        }}

        .filter-btn {{
            padding: 0.4rem 0.8rem;
            border: 1px solid var(--border);
            border-radius: 20px;
            background: var(--card-bg);
            color: var(--text-light);
            font-family: inherit;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .filter-btn:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}

        .filter-btn.active {{
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }}

        /* ===== Layout ===== */
        .layout {{
            max-width: 1100px;
            margin: 0 auto;
            display: flex;
            gap: 1.5rem;
            padding: 1.5rem;
        }}

        .sidebar {{
            width: 220px;
            flex-shrink: 0;
            position: sticky;
            top: calc(var(--controls-height) + 12px);
            height: fit-content;
            max-height: calc(100vh - var(--controls-height) - 24px);
            overflow-y: auto;
        }}

        .sidebar h3 {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-light);
            margin-bottom: 0.8rem;
            padding-bottom: 0.4rem;
            border-bottom: 1px solid var(--border);
        }}

        .nav-link {{
            display: block;
            padding: 0.35rem 0.6rem;
            margin-bottom: 0.2rem;
            color: var(--text);
            text-decoration: none;
            font-size: 0.85rem;
            border-radius: 4px;
            transition: all 0.15s;
        }}

        .nav-link:hover {{
            background: var(--accent-light);
            color: var(--accent-dark);
        }}

        .main-content {{
            flex: 1;
            min-width: 0;
        }}

        /* ===== Recipe Cards ===== */
        .recipe-card {{
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: var(--shadow);
            margin-bottom: 1.5rem;
            overflow: hidden;
            transition: box-shadow 0.2s;
            border: 1px solid var(--border);
            scroll-margin-top: calc(var(--controls-height) + 16px);
        }}

        .recipe-card:hover {{
            box-shadow: var(--shadow-hover);
        }}

        .card-header {{
            padding: 1.2rem 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .card-header h2 {{
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--accent-dark);
        }}

        .badge {{
            font-size: 0.7rem;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-family: system-ui, sans-serif;
            font-weight: 500;
        }}

        .badge-typed {{ background: #e8f5e8; color: var(--typed-badge); }}
        .badge-handwritten {{ background: #f5e8e8; color: var(--handwritten-badge); }}
        .badge-mixed {{ background: #e8e8f5; color: var(--mixed-badge); }}

        /* Card content: text on left, photos on right */
        .card-content {{
            display: flex;
            gap: 1.5rem;
            padding: 1.5rem;
        }}

        .card-text {{
            flex: 1;
            min-width: 0;
        }}

        .card-photos {{
            flex: 0 0 280px;
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }}

        .ingredients-section h3,
        .method-section h3 {{
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--accent);
            margin-bottom: 0.8rem;
            font-family: system-ui, sans-serif;
        }}

        .ingredients-list {{
            list-style: none;
            padding: 0;
        }}

        .ingredients-list li {{
            padding: 0.3rem 0;
            padding-left: 1.2rem;
            position: relative;
            font-size: 0.95rem;
        }}

        .ingredients-list li::before {{
            content: '\\2022';
            color: var(--accent);
            position: absolute;
            left: 0;
            font-weight: bold;
        }}

        .ingredients-list li.ingredient-section {{
            font-weight: 600;
            color: var(--accent-dark);
            padding-left: 0;
            margin-top: 0.8rem;
            margin-bottom: 0.3rem;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .ingredients-list li.ingredient-section::before {{
            content: none;
        }}

        .ingredients-list li.ingredient-instruction {{
            font-style: italic;
            color: var(--text-light);
        }}

        .handwritten-note {{
            background: #fff8e7;
            padding: 0.1rem 0.3rem;
            border-radius: 3px;
            font-style: italic;
            color: #8b6914;
            font-size: 0.88rem;
        }}

        .method-section {{
            margin-top: 1.2rem;
            padding-top: 1.2rem;
            border-top: 1px solid var(--border);
        }}

        .method-section p {{
            margin-bottom: 0.8rem;
            font-size: 0.95rem;
        }}

        .method-subsection {{
            font-size: 0.95rem;
            color: var(--accent-dark);
            margin: 1rem 0 0.5rem;
        }}

        .method-list {{
            margin: 0.5rem 0;
            padding-left: 1.5rem;
        }}

        .method-list li {{
            margin-bottom: 0.3rem;
            font-size: 0.95rem;
        }}

        .recipe-notes {{
            margin-top: 1rem;
            padding: 0.8rem 1rem;
            background: #f8f4ee;
            border-radius: 8px;
            font-size: 0.88rem;
            color: var(--text-light);
            border-left: 3px solid var(--accent-light);
        }}

        /* ===== Original Photos (shown by default) ===== */
        .original-photo {{
            cursor: pointer;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border);
            transition: box-shadow 0.2s;
            position: relative;
        }}

        .original-photo:hover {{
            box-shadow: var(--shadow-hover);
        }}

        .original-photo img {{
            width: 100%;
            display: block;
            border-radius: 7px;
        }}

        .photo-caption {{
            display: block;
            text-align: center;
            font-size: 0.7rem;
            color: var(--text-light);
            padding: 0.3rem;
            font-family: system-ui, sans-serif;
        }}

        .no-photo {{
            color: var(--text-light);
            font-style: italic;
            font-size: 0.85rem;
        }}

        /* ===== Lightbox ===== */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            cursor: pointer;
        }}

        .lightbox.open {{
            display: flex;
        }}

        .lightbox img {{
            max-width: 92vw;
            max-height: 92vh;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }}

        .lightbox-close {{
            position: absolute;
            top: 1rem;
            right: 1.5rem;
            color: white;
            font-size: 2rem;
            cursor: pointer;
            background: none;
            border: none;
            opacity: 0.8;
            font-family: system-ui, sans-serif;
        }}

        .lightbox-close:hover {{
            opacity: 1;
        }}

        /* ===== Mobile Nav Toggle Button ===== */
        .mobile-nav-toggle {{
            display: none; /* hidden on desktop */
            align-items: center;
            gap: 0.35rem;
            padding: 0.4rem 0.8rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--card-bg);
            color: var(--text-light);
            font-family: system-ui, sans-serif;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .mobile-nav-toggle:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}

        .mobile-nav-toggle.active {{
            background: var(--accent-light);
            border-color: var(--accent);
            color: var(--accent-dark);
        }}

        .mobile-nav-toggle .chevron {{
            transition: transform 0.2s;
        }}

        .mobile-nav-toggle.active .chevron {{
            transform: rotate(180deg);
        }}

        /* ===== Mobile Nav Dropdown ===== */
        .mobile-nav {{
            display: none; /* hidden on desktop; set to block on mobile via media query */
            position: fixed;
            left: 0;
            right: 0;
            top: 0; /* JS will set this to the controls bar bottom edge */
            background: var(--card-bg);
            border-bottom: 2px solid var(--border);
            box-shadow: 0 4px 16px rgba(61, 46, 31, 0.15);
            z-index: 99;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}

        .mobile-nav.open {{
            max-height: 70vh;
            overflow-y: auto;
        }}

        .mobile-nav-links {{
            padding: 0.6rem 1rem;
        }}

        .mobile-nav-link {{
            display: block;
            padding: 0.6rem 0.8rem;
            color: var(--text);
            text-decoration: none;
            font-size: 0.95rem;
            border-radius: 6px;
            border-bottom: 1px solid var(--border);
            transition: background 0.15s;
        }}

        .mobile-nav-link:last-child {{
            border-bottom: none;
        }}

        .mobile-nav-link:hover, .mobile-nav-link:active {{
            background: var(--accent-light);
            color: var(--accent-dark);
        }}

        /* ===== Responsive ===== */
        @media (max-width: 900px) {{
            .card-content {{
                flex-direction: column;
            }}

            .card-photos {{
                flex: none;
                flex-direction: row;
                flex-wrap: wrap;
            }}

            .original-photo {{
                flex: 1;
                min-width: 200px;
            }}
        }}

        @media (max-width: 768px) {{
            .sidebar {{ display: none; }}

            .mobile-nav-toggle {{ display: inline-flex; }}

            .mobile-nav {{ display: block; }}

            .mobile-nav-links {{ columns: 1; }}

            .layout {{ padding: 0.8rem; }}

            .site-header h1 {{ font-size: 1.7rem; }}

            .card-header h2 {{ font-size: 1.1rem; }}

            .card-content {{ padding: 1rem; }}

            .controls {{ padding: 0.6rem 0.8rem; }}

            .banner-photo {{ width: 100px; height: 100px; }}

            .card-photos {{ flex: none; }}
        }}

        /* ===== Print ===== */
        @media print {{
            .controls, .sidebar, .lightbox, .mobile-nav, .mobile-nav-toggle, .site-header::before, .banner-photos, .photo-caption {{
                display: none !important;
            }}

            .site-header {{
                background: none;
                color: var(--text);
                padding: 1rem;
                border-bottom: 2px solid var(--accent);
            }}

            .recipe-card {{
                box-shadow: none;
                border: 1px solid #ccc;
                page-break-inside: avoid;
            }}

            .card-content {{
                flex-direction: column;
            }}

            .card-photos {{
                flex: none;
            }}

            .original-photo {{
                max-width: 300px;
            }}

            body {{ background: white; }}
        }}

        /* ===== Smooth scroll ===== */
        html {{
            scroll-behavior: smooth;
        }}

        /* ===== No results ===== */
        .no-results {{
            text-align: center;
            padding: 3rem 1rem;
            color: var(--text-light);
            font-style: italic;
        }}

        .no-results.hidden {{ display: none; }}
    </style>
</head>
<body>

<header class="site-header">
    <h1>Nanny&rsquo;s Recipes</h1>
    <p class="subtitle">(At least the bits she wrote down!)</p>
    {banner_html}
</header>

<div class="controls" id="controlsBar">
    <input type="text" class="search-box" id="searchBox" placeholder="Search recipes..." oninput="filterRecipes()">
    <button class="mobile-nav-toggle" id="mobileNavToggle" onclick="toggleMobileNav()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 6h18M3 18h18"/></svg>
        Recipes
        <svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
    </button>
    <button class="filter-btn active" data-filter="all" onclick="setFilter('all', this)">All</button>
    <button class="filter-btn" data-filter="typed" onclick="setFilter('typed', this)">Typed</button>
    <button class="filter-btn" data-filter="handwritten" onclick="setFilter('handwritten', this)">Handwritten</button>
    <button class="filter-btn" data-filter="mixed" onclick="setFilter('mixed', this)">Mixed</button>
</div>

<!-- Mobile recipe navigation (hidden on desktop, collapsible on mobile) -->
<div class="mobile-nav" id="mobileNav">
    <div class="mobile-nav-links">
        {mobile_nav_html}
    </div>
</div>

<div class="layout">
    <nav class="sidebar">
        <h3>Recipes</h3>
        {nav_html}
    </nav>

    <main class="main-content">
        {cards_html}
        <div class="no-results hidden" id="noResults">
            No recipes match your search.
        </div>
    </main>
</div>

<!-- Lightbox for enlarged photos -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
    <img id="lightboxImg" src="" alt="Enlarged recipe photo">
</div>

<script>
    let currentFilter = 'all';

    function filterRecipes() {{
        const query = document.getElementById('searchBox').value.toLowerCase().trim();
        const cards = document.querySelectorAll('.recipe-card');
        let visibleCount = 0;

        cards.forEach(card => {{
            const title = card.dataset.title;
            const type = card.dataset.type;
            const matchesSearch = !query || title.includes(query) || card.textContent.toLowerCase().includes(query);
            const matchesFilter = currentFilter === 'all' || type === currentFilter;

            if (matchesSearch && matchesFilter) {{
                card.style.display = '';
                visibleCount++;
            }} else {{
                card.style.display = 'none';
            }}
        }});

        document.getElementById('noResults').classList.toggle('hidden', visibleCount > 0);
    }}

    function setFilter(filter, btn) {{
        currentFilter = filter;
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterRecipes();
    }}

    function openLightbox(src) {{
        document.getElementById('lightboxImg').src = src;
        document.getElementById('lightbox').classList.add('open');
        document.body.style.overflow = 'hidden';
    }}

    function closeLightbox() {{
        document.getElementById('lightbox').classList.remove('open');
        document.body.style.overflow = '';
    }}

    function positionMobileNav() {{
        const controls = document.getElementById('controlsBar');
        const nav = document.getElementById('mobileNav');
        if (controls && nav) {{
            nav.style.top = controls.getBoundingClientRect().bottom + 'px';
        }}
    }}

    function toggleMobileNav() {{
        const nav = document.getElementById('mobileNav');
        const btn = document.getElementById('mobileNavToggle');
        const isOpen = nav.classList.contains('open');
        if (!isOpen) positionMobileNav();
        nav.classList.toggle('open', !isOpen);
        btn.classList.toggle('active', !isOpen);
    }}

    function closeMobileNav() {{
        document.getElementById('mobileNav').classList.remove('open');
        document.getElementById('mobileNavToggle').classList.remove('active');
    }}

    function scrollToRecipe(id) {{
        closeMobileNav();
        const el = document.getElementById(id);
        if (!el) return;
        const controls = document.getElementById('controlsBar');
        const offset = controls ? controls.getBoundingClientRect().height + 12 : 60;
        const targetY = el.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({{ top: targetY, behavior: 'smooth' }});
    }}

    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') {{ closeLightbox(); closeMobileNav(); }}
    }});

    window.addEventListener('scroll', function() {{
        if (document.getElementById('mobileNav').classList.contains('open')) {{
            positionMobileNav();
        }}
    }}, {{ passive: true }});
</script>

</body>
</html>'''

    # Write the HTML file
    print(f"Writing HTML ({len(html) // 1024}KB)...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDone! Output: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / (1024*1024):.1f} MB")


if __name__ == "__main__":
    build_html()
