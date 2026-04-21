# Kvota OneStack - FastAPI application (uvicorn)
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies for WeasyPrint (PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint dependencies
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    # Fonts for PDF
    fonts-liberation \
    fonts-dejavu-core \
    # Build tools (for some Python packages)
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first (for Docker cache optimization)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5001

# Health check — hit the FastAPI liveness endpoint (docker-compose mirrors this)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/api/health')" || exit 1

# Run the application — pure FastAPI via uvicorn (Phase 6C-3, 2026-04-21).
# `api.app:api_app` is the outer FastAPI app that mounts the router sub-app at /api.
CMD ["uvicorn", "api.app:api_app", "--host", "0.0.0.0", "--port", "5001"]
