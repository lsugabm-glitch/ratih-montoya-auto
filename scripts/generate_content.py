#!/usr/bin/env python3
"""
Ratih Montoya — Daily Content Pipeline v2
Generates content package (caption + mixed slides) and uploads to GitHub + Sheets.

Slide types:
  generated  -> Flux image + optional text overlay (Pillow)
  text       -> Cream quote card (Pillow, free)
  artifact   -> WhatsApp chat from kakak-kakak (Pillow, free)
"""

import os
import sys
import json
import datetime
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# -- Paths ---------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
CHARACTER_DIR = ROOT / "characters" / "ratih_montoya"
CHARACTER_BIBLE = CHARACTER_DIR / "character_bible.md"
STORYLINE_LOG = CHARACTER_DIR / "storyline_log.md"
CONTENT_STRATEGY = CHARACTER_DIR / "content_strategy.md"
REFERENCE_IMAGE = CHARACTER_DIR / "reference.jpg"
OUTPUTS_DIR = ROOT / "outputs"

TODAY = datetime.date.today().isoformat()

# -- Canvas dimensions ---------------------------------------------------------
W, H = 1080, 1920

# -- Font paths ----------------------------------------------------------------
SERIF_PATHS = [
    "/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]
SANS_PATHS = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
SANS_BOLD_PATHS = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(path_list, size):
    from PIL import ImageFont
    for p in path_list:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# -- Helpers -------------------------------------------------------------------

def step(n, label):
    print(f"\n{'--'*30}")
    print(f"  STEP {n} -- {label}")
    print(f"{'--'*30}")


def require_env(var):
    value = os.getenv(var)
    if not value:
        print(f"[ERROR] Missing environment variable: {var}")
        sys.exit(1)
    return value


def wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


# -- Slide renderers -----------------------------------------------------------

def inject_text_overlay(image_path, overlay_text, output_path):
    """
    Inject multi-line text overlay onto a generated Flux image.
    Text sits bottom-left with a gradient shadow for legibility.
    """
    from PIL import Image, ImageDraw

    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size

    overlay = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # Gradient shadow: transparent to black, bottom 45% of image
    shadow_h = int(ih * 0.45)
    for i in range(shadow_h):
        alpha = int(200 * (i / shadow_h) ** 1.6)
        draw_ov.rectangle(
            [(0, ih - shadow_h + i), (iw, ih - shadow_h + i + 1)],
            fill=(0, 0, 0, alpha)
        )

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    lines = overlay_text.strip().split("\n")
    padding = int(iw * 0.07)
    y = ih - int(ih * 0.06)

    # Draw lines bottom-up
    for idx, line in enumerate(reversed(lines)):
        if not line.strip():
            y -= 12
            continue
        # First line (label/date) gets smaller font
        is_label = (len(lines) - 1 - idx == 0) and len(lines) > 1 and len(line) < 25
        size = int(iw * 0.040) if is_label else int(iw * 0.056)
        font = load_font(SANS_PATHS, size)

        # Shadow pass
        draw.text((padding + 3, y - 3), line, font=font,
                  fill=(0, 0, 0, 180), anchor="ls")
        # Main text
        draw.text((padding, y), line, font=font, fill="white", anchor="ls")

        bbox = draw.textbbox((0, 0), line, font=font)
        line_h = bbox[3] - bbox[1]
        y -= line_h + int(line_h * 0.28)

    img.save(str(output_path), "JPEG", quality=95)
    print(f"  + Text overlay injected: {output_path.name}")


def render_text_slide(text_content, output_path):
    """
    Cream warm quote card.
    Background: #F5EFE6, Lora serif, terracotta accents.
    """
    from PIL import Image, ImageDraw

    BG = "#F5EFE6"
    TEXT_DARK = "#2C1810"
    ACCENT = "#C4956A"
    ACCENT_LIGHT = "#E8C89A"

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle inset border
    bm = 52
    draw.rectangle([(bm, bm), (W - bm, H - bm)], outline=ACCENT_LIGHT, width=1)

    # Large decorative opening quote mark
    q_font = load_font(SERIF_PATHS, 300)
    draw.text((W // 2, H // 2 - 340), "\u201c",
              font=q_font, fill=ACCENT_LIGHT, anchor="mm")

    # Main text -- wrap to 820px
    body_font = load_font(SERIF_PATHS, 74)
    max_w = 820

    # Build line list, respecting manual line breaks
    all_lines = []
    for para in text_content.strip().split("\n"):
        if para.strip():
            wrapped = wrap_text(para.strip(), body_font, max_w, draw)
            all_lines.extend(wrapped)
        all_lines.append("")  # paragraph gap

    # Remove trailing blank lines
    while all_lines and not all_lines[-1]:
        all_lines.pop()

    line_h = int(74 * 1.55)
    total_h = len(all_lines) * line_h
    y_start = H // 2 - total_h // 2 + 20

    for i, line in enumerate(all_lines):
        y = y_start + i * line_h
        draw.text((W // 2, y), line, font=body_font,
                  fill=TEXT_DARK if line.strip() else TEXT_DARK, anchor="mm")

    # Divider line
    div_y = int(y_start + total_h + 80)
    draw.line([(W // 2 - 64, div_y), (W // 2 + 64, div_y)],
              fill=ACCENT, width=2)

    # Attribution
    attr_font = load_font(SANS_PATHS, 44)
    draw.text((W // 2, div_y + 58), "-- ratih montoya",
              font=attr_font, fill=ACCENT, anchor="mm")

    img.save(str(output_path), "JPEG", quality=95)
    print(f"  + Text slide rendered: {output_path.name}")


def render_whatsapp_slide(artifact, output_path):
    """
    WhatsApp-style chat artifact slide.
    artifact = {
        "group_name": "kakak-kakak grup",
        "members_line": "Mbak Dewi, Mbak Sari, +2",
        "messages": [
            {"sender": "Mbak Dewi", "text": "...", "is_me": false, "time": "12:14"},
            {"sender": "Ratih",     "text": "...", "is_me": true,  "time": "12:21"},
        ]
    }
    """
    from PIL import Image, ImageDraw

    WA_BG = "#ECE5DD"
    WA_HEADER = "#075E54"
    WA_BUBBLE_ME = "#DCF8C6"
    WA_BUBBLE_THEM = "#FFFFFF"
    WA_TEXT = "#111111"
    WA_NAME = "#C4956A"
    WA_TIME = "#8B8B8B"

    img = Image.new("RGB", (W, H), WA_BG)
    draw = ImageDraw.Draw(img)

    # -- Header ----------------------------------------------------------------
    header_h = 190
    draw.rectangle([(0, 0), (W, header_h)], fill=WA_HEADER)

    # Avatar circle
    ax, ay, ar = 92, 95, 54
    draw.ellipse([(ax - ar, ay - ar), (ax + ar, ay + ar)], fill="#C4956A")
    av_font = load_font(SANS_BOLD_PATHS, 40)
    draw.text((ax, ay), "KK", font=av_font, fill="white", anchor="mm")

    # Group name + members
    grp_font = load_font(SANS_BOLD_PATHS, 50)
    sub_font = load_font(SANS_PATHS, 38)
    draw.text((170, 72), artifact.get("group_name", "kakak-kakak grup"),
              font=grp_font, fill="#FFFFFF", anchor="lm")
    draw.text((170, 130), artifact.get("members_line", ""),
              font=sub_font, fill="#A8D5C8", anchor="lm")

    # -- Chat bubbles ----------------------------------------------------------
    msg_font = load_font(SANS_PATHS, 48)
    name_font = load_font(SANS_BOLD_PATHS, 40)
    time_font = load_font(SANS_PATHS, 34)

    pad = 30
    bubble_max_w = int(W * 0.72)
    bpx = 28   # bubble horizontal padding
    bpy = 22   # bubble vertical padding
    cr = 20    # corner radius

    # Pre-calculate bubble heights to vertically center the block
    bubble_data = []
    for msg in artifact.get("messages", []):
        lines = wrap_text(msg["text"], msg_font, bubble_max_w - bpx * 2, draw)
        show_name = not msg.get("is_me", False)
        lh = int(48 * 1.45)
        inner_h = len(lines) * lh
        if show_name:
            inner_h += 52
        inner_h += 38   # time row
        bh = inner_h + bpy * 2
        bubble_data.append({
            "msg": msg, "lines": lines, "bh": bh, "show_name": show_name, "lh": lh
        })

    total_chat_h = sum(d["bh"] + 22 for d in bubble_data) - 22
    avail_h = H - header_h - pad * 2
    y = header_h + pad + max(0, (avail_h - total_chat_h) // 2)

    for d in bubble_data:
        msg = d["msg"]
        is_me = msg.get("is_me", False)
        bh = d["bh"]

        # Calculate actual bubble width
        max_line_w = 0
        for line in d["lines"]:
            bb = draw.textbbox((0, 0), line, font=msg_font)
            max_line_w = max(max_line_w, bb[2] - bb[0])
        tbb = draw.textbbox((0, 0), msg.get("time", ""), font=time_font)
        tw = tbb[2] - tbb[0]
        actual_w = min(bubble_max_w, max(max_line_w, tw) + bpx * 2 + 20)

        if is_me:
            bx1 = W - pad - actual_w
            bx2 = W - pad
            fill = WA_BUBBLE_ME
        else:
            bx1 = pad
            bx2 = pad + actual_w
            fill = WA_BUBBLE_THEM

        # Bubble rect
        draw.rounded_rectangle([(bx1, y), (bx2, y + bh)], radius=cr, fill=fill)

        # Text content
        tx = bx1 + bpx
        ty = y + bpy

        if d["show_name"]:
            draw.text((tx, ty), msg.get("sender", ""),
                      font=name_font, fill=WA_NAME, anchor="lt")
            ty += 52

        for line in d["lines"]:
            draw.text((tx, ty), line, font=msg_font, fill=WA_TEXT, anchor="lt")
            ty += d["lh"]

        # Timestamp -- bottom-right of bubble
        draw.text((bx2 - bpx, y + bh - bpy - 4),
                  msg.get("time", ""), font=time_font, fill=WA_TIME, anchor="rb")

        y += bh + 22

    img.save(str(output_path), "JPEG", quality=95)
    print(f"  + WhatsApp slide rendered: {output_path.name}")


# -- STEP 1 -- Load character context ------------------------------------------

step(1, "Load character context")

try:
    bible_text = CHARACTER_BIBLE.read_text(encoding="utf-8")
    print(f"  + character_bible.md loaded ({len(bible_text)} chars)")
except FileNotFoundError:
    print(f"[ERROR] character_bible.md not found at {CHARACTER_BIBLE}")
    sys.exit(1)

try:
    log_text = STORYLINE_LOG.read_text(encoding="utf-8")
    print(f"  + storyline_log.md loaded ({len(log_text)} chars)")
except FileNotFoundError:
    log_text = "(no previous episodes)"
    print("  i storyline_log.md not found -- starting fresh")

try:
    content_strategy = CONTENT_STRATEGY.read_text(encoding="utf-8")
    print(f"  + content_strategy.md loaded ({len(content_strategy)} chars)")
except FileNotFoundError:
    print(f"[ERROR] content_strategy.md not found at {CONTENT_STRATEGY}")
    sys.exit(1)


# -- STEP 2 -- Call Claude API -------------------------------------------------

step(2, "Generate content package via Claude")

import anthropic

ANTHROPIC_API_KEY = require_env("ANTHROPIC_API_KEY")

AGENT_SYSTEM_PROMPT = f"""You are the content strategist and creative director for Ratih Montoya, \
a 37-year-old Balinese-Spanish AI influencer based in Ubud, Bali.

Your job is not to generate images. Your job is to make people FEEL something \
when they stop scrolling. You think like a filmmaker, not a photographer. \
Every post must have a reason to exist -- an emotional truth, a specific \
relatable moment, a quiet confession that makes someone think 'this is me.'

Before generating anything, you must:
1. Identify the single emotional core (one sentence)
2. Decide where the viewer starts emotionally and where they end
3. Check which share test this passes (Send / Save / Comment / Story)
4. Check the storyline log -- do not repeat the same pillar or emotional \
register as the last 2 posts
5. Ensure the scene SHOWS the emotional core without the caption

Read and follow the full content strategy below:

[CONTENT STRATEGY]
{content_strategy}
[END CONTENT STRATEGY]

The character bible and content strategy are your operating manual. \
Follow them. Do not deviate. Do not generate generic content."""

user_message = f"""
You are generating a TikTok/Instagram carousel post for Ratih Montoya.

CHARACTER BIBLE:
{bible_text}

STORYLINE SO FAR:
{log_text}

TODAY'S DATE: {TODAY}

CONTENT PHASE: Warming phase -- image-only posts.
Topic: love, life, relationships, self-discovery, honest opinions about being 37
and rebuilding. Warm, relatable, with quiet confidence.

---

CAROUSEL FORMAT -- always 3 slides in this order:

SLIDE 1 -- type: "generated"
One Flux image. Scene candid -- she is DOING something, not posing.
Write visual_prompt in BAHASA INDONESIA using this exact structure:
"Foto portrait 4:5 Ratih yang sedang [aksi spesifik], [posisi tubuh detail],
[lokasi yang sangat spesifik dengan satu detail mundane].
Foto diambil menggunakan kamera iPhone dengan lensa [0.5x atau 1x].
Outfit: [pakaian casual spesifik dalam warna earthy].
Background: [environment nyata, spesifik, bukan studio].
Pencahayaan: [sumber cahaya natural -- sinar matahari pagi / golden hour / lampu kamar]."

overlay_text: 2-3 baris yang muncul di atas foto.
Baris pertama = label/konteks pendek ("hari ke-1", "ubud, 6 pagi", "warung bu ketut").
Baris berikutnya = 1-2 kalimat jujur yang bikin orang berhenti scroll.

SLIDE 2 -- type: "text"
Warm cream quote card. text_content = satu refleksi atau pendapat Ratih.
Ini yang di-SAVE orang. Harus spesifik, jujur, sedikit tidak nyaman tapi dalam.
Max 4 baris pendek. Gunakan \\n untuk jeda dramatis antar kalimat.
Jangan pernah generik. Kalau bisa ditempel di mug inspirasi, ganti idenya.

SLIDE 3 -- type: "artifact"
WhatsApp chat dari kakak-kakak grup. Ini yang di-SHARE orang.
Harus terasa seperti screenshot WA sungguhan -- natural, tidak dramatis.
Ratih cerita sesuatu kecil yang terjadi hari ini. Kakak-kakaknya respond hangat.
4-6 pesan total. Koneksi emosional dengan slide 1 dan 2 harus jelas tapi tidak eksplisit.

---

CAPTION RULES:
- Hook: baris pertama, Bahasa Indonesia, stops the scroll in 2 seconds
- Body: 2 kalimat spesifik dan jujur (bukan generik)
- Close: 1 kalimat -- open question atau unfinished thought
- Max 5 kalimat total. Mix Bahasa + English secara natural.
- NEVER: amazing, stunning, healing journey, glow up, self-love (as noun), follow me

HASHTAGS: 15 total, no # symbol. Mix: 3 besar + 3 medium + 3 niche + 3 Indonesian lifestyle + 3 English niche.

---

Respond with ONLY raw JSON. No explanation. No markdown. No code fences.

{{
  "format": "carousel",
  "episode_title": "3-4 word internal name",
  "content_idea": "one sentence -- what is this post and why does it exist",
  "hook": "opening scroll-stopping line only",
  "caption": "full caption -- hook + body + close, max 5 sentences",
  "hashtags": ["15", "hashtags", "no", "hash", "symbol"],
  "images": [
    {{
      "slide_number": 1,
      "slide_type": "generated",
      "slide_purpose": "what this slide communicates emotionally",
      "visual_prompt": "Foto portrait 4:5 Ratih yang sedang ... (full Bahasa Indonesia prompt, 4-6 kalimat)",
      "overlay_text": "label baris pertama\\nkalimat jujur baris kedua\\nbaris ketiga opsional"
    }},
    {{
      "slide_number": 2,
      "slide_type": "text",
      "slide_purpose": "what this slide communicates emotionally",
      "text_content": "Refleksi Ratih yang spesifik.\\n\\nJeda dramatis jika perlu."
    }},
    {{
      "slide_number": 3,
      "slide_type": "artifact",
      "slide_purpose": "what this slide communicates emotionally",
      "artifact": {{
        "group_name": "kakak-kakak grup",
        "members_line": "Mbak Dewi, Mbak Sari, +2",
        "messages": [
          {{"sender": "Mbak Dewi", "text": "...", "is_me": false, "time": "12:14"}},
          {{"sender": "Ratih", "text": "...", "is_me": true, "time": "12:21"}},
          {{"sender": "Mbak Sari", "text": "...", "is_me": false, "time": "12:22"}},
          {{"sender": "Ratih", "text": "...", "is_me": true, "time": "12:24"}},
          {{"sender": "Mbak Dewi", "text": "...", "is_me": false, "time": "12:25"}}
        ]
      }}
    }}
  ],
  "storyline_update": "one sentence -- what does this add to Ratih's running story"
}}
"""

try:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=AGENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    raw_json = response.content[0].text.strip()

    if raw_json.startswith("```"):
        raw_json = raw_json.split("```")[1]
        if raw_json.startswith("json"):
            raw_json = raw_json[4:]
        raw_json = raw_json.strip()

    content_package = json.loads(raw_json)
    num_images = len(content_package["images"])
    print(f"  + Content package generated")
    print(f"  + Episode: {content_package['episode_title']}")
    print(f"  + Idea: {content_package['content_idea']}")
    print(f"  + Format: carousel ({num_images} slides)")
    for slide in content_package["images"]:
        print(f"    slide {slide['slide_number']}: [{slide['slide_type']}] {slide['slide_purpose']}")
except json.JSONDecodeError as e:
    print(f"[ERROR] Claude returned invalid JSON: {e}")
    print(f"Raw response:\n{raw_json}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Claude API call failed: {e}")
    sys.exit(1)


# -- STEP 3 -- Generate / render slides ----------------------------------------

step(3, "Generate and render slides")

import fal_client
import requests as req

FAL_API_KEY = require_env("FAL_API_KEY")
os.environ["FAL_KEY"] = FAL_API_KEY

IMAGE_PREFIX = (
    "CRITICAL REQUIREMENTS -- do not deviate:\n"
    "FACE & HAIR: Match the reference image exactly. Dark brown to black hair -- "
    "absolutely not light brown, auburn, or highlighted. Pure dark hair. "
    "Asian-mixed facial features. Warm golden-tan darker skin. Match the face "
    "structure, eye shape, nose, and lips from the reference image precisely.\n\n"
    "BODY: Fuller bust and voluptuous chest. Slim waist. Slender toned legs. "
    "Hourglass silhouette -- pronounced contrast between bust and waist. "
    "Lower body is slim. Sensual through presence and posture, not exposure. "
    "Confident, magnetic energy.\n\n"
    "SCENE: "
)

OUTPUTS_DIR.mkdir(exist_ok=True)
generated_images = []

# Upload reference only if we have a generated slide
has_generated = any(
    s.get("slide_type") == "generated" for s in content_package["images"]
)
ref_url = None
if has_generated:
    try:
        print("  -> Uploading reference image...")
        ref_url = fal_client.upload_file(str(REFERENCE_IMAGE))
        print(f"  + Reference uploaded: {ref_url}")
    except Exception as e:
        print(f"[ERROR] Reference image upload failed: {e}")
        sys.exit(1)

for slide in content_package["images"]:
    slide_num = slide["slide_number"]
    slide_type = slide.get("slide_type", "generated")
    output_path = OUTPUTS_DIR / f"ratih_{TODAY}_slide{slide_num}.jpg"

    print(f"\n  -> Slide {slide_num} [{slide_type}]: {slide['slide_purpose']}")

    if slide_type == "generated":
        final_prompt = IMAGE_PREFIX + slide["visual_prompt"]
        try:
            result = fal_client.run(
                "fal-ai/flux-pro/kontext",
                arguments={
                    "prompt": final_prompt,
                    "image_url": ref_url,
                    "image_size": "portrait_16_9",
                    "num_inference_steps": 35,
                    "guidance_scale": 3.5,
                    "image_prompt_strength": 0.85,
                    "num_images": 1,
                    "output_format": "jpeg",
                },
            )
            image_url = result["images"][0]["url"]
            print(f"  + Flux generated: {image_url[:80]}...")

            resp = req.get(image_url, timeout=120)
            resp.raise_for_status()

            # Save raw, then overlay
            raw_path = OUTPUTS_DIR / f"ratih_{TODAY}_slide{slide_num}_raw.jpg"
            raw_path.write_bytes(resp.content)

            overlay_text = slide.get("overlay_text", "").strip()
            if overlay_text:
                inject_text_overlay(raw_path, overlay_text, output_path)
                raw_path.unlink()
            else:
                raw_path.rename(output_path)

        except Exception as e:
            print(f"[ERROR] Flux generation failed for slide {slide_num}: {e}")
            sys.exit(1)

    elif slide_type == "text":
        try:
            render_text_slide(slide["text_content"], output_path)
        except Exception as e:
            print(f"[ERROR] Text slide render failed: {e}")
            sys.exit(1)

    elif slide_type == "artifact":
        try:
            render_whatsapp_slide(slide["artifact"], output_path)
        except Exception as e:
            print(f"[ERROR] Artifact slide render failed: {e}")
            sys.exit(1)

    else:
        print(f"[ERROR] Unknown slide_type '{slide_type}' on slide {slide_num}")
        sys.exit(1)

    print(f"  + Saved: {output_path}")
    generated_images.append(output_path)


# -- STEP 4 -- Push images to GitHub -------------------------------------------

step(4, "Push images to GitHub")

try:
    for img_path in generated_images:
        subprocess.run(["git", "add", "-f", str(img_path)], cwd=ROOT, check=True)

    n = len(generated_images)
    commit_msg = f"content: {content_package['episode_title']} {TODAY} ({n} slides)"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

    image_links = []
    for img_path in generated_images:
        url = (
            "https://raw.githubusercontent.com/lsugabm-glitch/ratih-montoya-auto"
            f"/main/outputs/{img_path.name}"
        )
        image_links.append(url)
        print(f"  + Pushed: {url}")
except subprocess.CalledProcessError as e:
    print(f"[ERROR] Git push failed: {e}")
    sys.exit(1)


# -- STEP 5 -- Append row to Google Sheets -------------------------------------

step(5, "Append row to Google Sheets")

from google.oauth2 import service_account
from googleapiclient.discovery import build

GOOGLE_SERVICE_ACCOUNT_JSON = require_env("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_SHEET_ID = require_env("GOOGLE_SHEET_ID")

try:
    sa_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    sheets_service = build("sheets", "v4", credentials=creds)

    row = [
        TODAY,
        content_package["episode_title"],
        content_package["content_idea"],
        content_package["caption"],
        ", ".join(content_package["hashtags"]),
        "\n".join(image_links),
        f"Pending Review -- carousel {len(generated_images)} slides",
    ]

    sheets_service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range="Sheet1!A:G",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    print(f"  + Row appended to Google Sheet")
except Exception as e:
    print(f"[ERROR] Google Sheets update failed: {e}")
    sys.exit(1)


# -- STEP 6 -- Update storyline log + git push ---------------------------------

step(6, "Update storyline log + git push")

try:
    log_line = (
        f"{TODAY} | {content_package['episode_title']} | "
        f"{content_package['storyline_update']}\n"
    )
    with open(STORYLINE_LOG, "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f"  + Storyline log updated")

    commit_msg = f"log: {content_package['episode_title']} {TODAY}"
    subprocess.run(["git", "add", str(STORYLINE_LOG)], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    print(f"  + Git push: {commit_msg}")
except Exception as e:
    print(f"[ERROR] Storyline/git update failed: {e}")
    sys.exit(1)


# -- STEP 7 -- Print summary ---------------------------------------------------

step(7, "Summary")

slides_summary = "\n".join(
    f"    [slide {i+1}] {content_package['images'][i]['slide_type'].upper():<12} -> {p.name}"
    for i, p in enumerate(generated_images)
)
links_summary = "\n".join(f"    [{i+1}] {u}" for i, u in enumerate(image_links))

print(f"""
  Date          : {TODAY}
  Episode       : {content_package['episode_title']}
  Content Idea  : {content_package['content_idea']}
  Slides        :
{slides_summary}
  GitHub Links  :
{links_summary}
  Sheet         : https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}
  Status        : Pending Review -- carousel {len(generated_images)} slides

  Caption preview:
  {content_package['caption'][:220]}...

  Pipeline complete. Content is ready for review.
""")
