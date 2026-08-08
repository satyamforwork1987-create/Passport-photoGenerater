# Passport Photo Maker

A Flask web app that lets a user:

1. Upload a photo
2. Automatically remove the background (AI-powered, via `rembg`)
3. Choose a background color — **White**, **Blue**, or **Sky Blue**
4. Choose the photo size (default: **Passport, 35x45mm**) — also supports Stamp, 2x2", and 4x6"
5. Choose the quantity of photos
6. Generate a print-ready **A4 PDF** with the photos tiled and cut guides, at 300 DPI

## Project structure

```
passport-photo-maker/
├── app.py                 # Flask backend
├── templates/
│   └── index.html         # Frontend page
├── static/
│   ├── style.css
│   └── script.js
├── requirements.txt
├── render.yaml             # Render deployment config
├── Procfile                 # Fallback start command
├── runtime.txt               # Python version pin
└── .gitignore
```

## Run locally (VS Code)

1. Open this folder in VS Code.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   python app.py
   ```
5. Open http://localhost:5000 in your browser.

> The first time you process a photo, `rembg` downloads its AI model
> (~176MB) to a local cache folder. This can take a minute — after that
> it's fast.

## Deploy to Render

### Option A — using `render.yaml` (recommended)

1. Push this project to a GitHub (or GitLab) repository.
2. In the Render dashboard, click **New +** → **Blueprint**, and select your repo.
   Render will read `render.yaml` automatically and configure everything
   (build command, start command, Python version).
3. Click **Apply** / **Create**. Render will:
   - Install dependencies
   - Pre-download the background-removal AI model during the build step
     (so the first user request isn't slow)
   - Start the app with `gunicorn`
4. Once deployed, open the Render-provided URL.

### Option B — manual Web Service setup

1. Push this project to GitHub.
2. In Render, click **New +** → **Web Service**, connect your repo.
3. Set:
   - **Environment**: Python 3
   - **Build Command**:
     ```
     pip install -r requirements.txt && python -c "from rembg import new_session; new_session('u2net')"
     ```
   - **Start Command**:
     ```
     gunicorn app:app --timeout 120 --workers 1
     ```
4. Deploy.

### Notes on the free tier

- The free plan has limited RAM/CPU; background removal is CPU-intensive.
  Keep `--workers 1` to avoid running out of memory. If you upgrade your
  plan, you can increase workers.
- Free instances spin down after inactivity — the first request after
  idling will be slower (cold start).
- Max upload size is capped at 15MB in `app.py` (`MAX_CONTENT_LENGTH`) —
  adjust if needed.

## Customization

- **Add more background colors**: edit the `COLORS` dict in `app.py` and
  add a matching `<label class="color-option">` block in
  `templates/index.html`.
- **Add more sizes**: edit the `SIZES` / `SIZE_LABELS` dicts in `app.py`.
- **Change sheet size from A4**: edit `A4_MM` in `app.py`.
- **Change print DPI**: edit `DPI` in `app.py`.
