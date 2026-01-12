# Kvota OneStack

**Proof of concept:** Single-language (Python) quotation platform using FastHTML.

## Why?

Testing if FastHTML + HTMX can replace the current Next.js + FastAPI stack to:
- Reduce integration bugs (single language)
- Better Claude Code assistance (Python > JavaScript)
- Simplify development for solo developer

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Run the app
python main.py

# Open browser
open http://localhost:5001
```

**Login:** `andrey@masterbearingsales.ru` / `password`

## What's Included

- **Login/Logout** - Session-based auth
- **Dashboard** - Stats cards and recent quotes
- **Quotes List** - Table with mock data
- **New Quote** - Form with file upload and HTMX interactions
- **Quote Detail** - View single quote

## Tech Stack

- **FastHTML** - Python web framework with HTMX built-in
- **Pico CSS** - Minimal CSS framework
- **HTMX** - Dynamic interactions without JavaScript

## Next Steps (if we proceed)

1. Connect to Supabase (same DB as current app)
2. Port calculation engine
3. Build remaining pages
4. Add real auth (Supabase Auth)

## File Structure

```
onestack/
├── main.py           # All routes and logic (single file for now)
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variables template
└── venv/             # Virtual environment
```
