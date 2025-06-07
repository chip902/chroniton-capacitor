FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and set permissions
RUN useradd -m appuser && \
    mkdir -p /app/storage && \
    chown -R appuser:appuser /app

# Copy requirements file to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt ./

# Install Python dependencies with compatible versions
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    # Install key dependencies first to ensure they're properly resolved
    pip install --no-cache-dir google-api-python-client==2.108.0 && \
    pip install --no-cache-dir google-auth==2.23.4 && \
    pip install --no-cache-dir aioredis==2.0.1 && \
    pip install --no-cache-dir redis==5.0.1 && \
    # Now install the rest of the requirements
    pip install --no-cache-dir -r requirements.txt && \
    # Verify all critical imports work properly
    python -c "import sys; print('Python version:', sys.version)" && \
    python -c "import googleapiclient; print('Google API client version:', googleapiclient.__version__)" && \
    python -c "import aioredis; print('Aioredis version:', aioredis.__version__)" && \
    python -c "import redis; print('Redis version:', redis.__version__)" && \
    # Verify installation
    echo "Installed packages:" && \
    pip freeze

# Copy application code
COPY --chown=appuser:appuser . .

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8008

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]