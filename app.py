import io
import os

# Must be set before onnxruntime/numpy/numba are imported — limits internal
# thread pools, which each carry their own memory overhead. On a
# memory-constrained instance (Render free tier), fewer threads means a
# smaller footprint, at the cost of slightly slower processing.
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('NUMEXPR_NUM_THREADS', '1')

from flask import Flask, request, render_template, send_file, jsonify
from PIL import Image, ImageDraw
from rembg import remove, new_session

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15 MB upload limit

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DPI = 300

# Photo sizes in millimeters (width, height)
SIZES = {
    'passport': (35, 45),   # standard passport photo (default)
    'stamp': (20, 25),      # stamp size
    '2x2': (51, 51),        # US visa / 2x2 inch
    '4x6': (102, 152),      # 4x6 inch print
}

SIZE_LABELS = {
    'passport': 'Passport (35 x 45 mm)',
    'stamp': 'Stamp (20 x 25 mm)',
    '2x2': '2x2 inch (51 x 51 mm)',
    '4x6': '4x6 inch (102 x 152 mm)',
}

# Background colors (RGB)
COLORS = {
    'white': (255, 255, 255),
    'blue': (0, 51, 153),
    'sky_blue': (135, 206, 235),
}

A4_MM = (210, 297)
SHEET_MARGIN_MM = 5
PHOTO_GAP_MM = 3

# Lazily-created rembg session (model loads on first use, cached afterwards)
# u2netp is a distilled, much smaller/lighter model than u2net (~4.7MB vs
# ~176MB) — used to keep memory usage low on Render's free tier.
_session = None


def get_session():
    global _session
    if _session is None:
        _session = new_session('u2netp')
    return _session


def mm_to_px(mm, dpi=DPI):
    return int(round(mm / 25.4 * dpi))


def fit_cover(img, target_w, target_h):
    """Resize + center-crop an image to exactly fill target_w x target_h."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


# Modern phone photos can be 3000-4000px wide / several MB. Running AI
# background removal at that resolution uses far more memory than a
# passport photo needs (final output is only ~500px wide at 300 DPI), and
# can exceed Render's free-tier RAM limit. Downscale before processing.
MAX_INPUT_DIMENSION = 1200


def downscale_if_needed(input_bytes):
    img = Image.open(io.BytesIO(input_bytes))
    img = img.convert('RGB')
    w, h = img.size
    if max(w, h) > MAX_INPUT_DIMENSION:
        scale = MAX_INPUT_DIMENSION / max(w, h)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()


def remove_background_and_recolor(input_bytes, color_key):
    """Remove background from the uploaded image and composite onto a solid color."""
    input_bytes = downscale_if_needed(input_bytes)
    output_bytes = remove(input_bytes, session=get_session())
    cutout = Image.open(io.BytesIO(output_bytes)).convert('RGBA')

    bg_rgb = COLORS.get(color_key, COLORS['white'])
    bg = Image.new('RGBA', cutout.size, bg_rgb + (255,))
    composited = Image.alpha_composite(bg, cutout).convert('RGB')
    return composited


def layout_on_a4(photo, quantity, photo_w_px, photo_h_px):
    """Tile copies of `photo` across one or more A4 pages."""
    a4_w_px = mm_to_px(A4_MM[0])
    a4_h_px = mm_to_px(A4_MM[1])
    margin_px = mm_to_px(SHEET_MARGIN_MM)
    gap_px = mm_to_px(PHOTO_GAP_MM)

    usable_w = a4_w_px - 2 * margin_px
    usable_h = a4_h_px - 2 * margin_px

    cols = max(1, (usable_w + gap_px) // (photo_w_px + gap_px))
    rows = max(1, (usable_h + gap_px) // (photo_h_px + gap_px))
    per_page = int(cols * rows)

    pages = []
    remaining = quantity
    while remaining > 0:
        page = Image.new('RGB', (a4_w_px, a4_h_px), (255, 255, 255))
        draw = ImageDraw.Draw(page)
        count_this_page = min(remaining, per_page)

        for i in range(count_this_page):
            r = i // cols
            c = i % cols
            x = margin_px + c * (photo_w_px + gap_px)
            y = margin_px + r * (photo_h_px + gap_px)
            page.paste(photo, (x, y))
            # light cut-guide border
            draw.rectangle(
                [x, y, x + photo_w_px - 1, y + photo_h_px - 1],
                outline=(190, 190, 190),
                width=1,
            )

        pages.append(page)
        remaining -= count_this_page

    return pages


def validate_upload(file):
    if file is None or file.filename == '':
        return 'No photo uploaded.'
    filename = file.filename.lower()
    if not (filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.png') or filename.endswith('.webp')):
        return 'Unsupported file type. Please upload a JPG, PNG, or WEBP image.'
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', sizes=SIZE_LABELS)


@app.route('/preview', methods=['POST'])
def preview():
    file = request.files.get('photo')
    error = validate_upload(file)
    if error:
        return jsonify({'error': error}), 400

    color_key = request.form.get('color', 'white')

    try:
        input_bytes = file.read()
        composited = remove_background_and_recolor(input_bytes, color_key)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': f'Could not process image: {exc}'}), 500

    buf = io.BytesIO()
    composited.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@app.route('/generate', methods=['POST'])
def generate():
    file = request.files.get('photo')
    error = validate_upload(file)
    if error:
        return jsonify({'error': error}), 400

    color_key = request.form.get('color', 'white')
    size_key = request.form.get('size', 'passport')
    if size_key not in SIZES:
        size_key = 'passport'

    try:
        quantity = int(request.form.get('quantity', 8))
    except ValueError:
        quantity = 8
    quantity = max(1, min(quantity, 100))

    try:
        input_bytes = file.read()
        composited = remove_background_and_recolor(input_bytes, color_key)

        w_mm, h_mm = SIZES[size_key]
        photo_w_px = mm_to_px(w_mm)
        photo_h_px = mm_to_px(h_mm)
        photo = fit_cover(composited, photo_w_px, photo_h_px)

        pages = layout_on_a4(photo, quantity, photo_w_px, photo_h_px)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': f'Could not generate photo sheet: {exc}'}), 500

    pdf_buffer = io.BytesIO()
    pages[0].save(
        pdf_buffer,
        format='PDF',
        save_all=True,
        append_images=pages[1:],
        resolution=DPI,
    )
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='passport_photos.pdf',
    )


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/ping')
def ping():
    return 'pong', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)