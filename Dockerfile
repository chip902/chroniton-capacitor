FROM python:3.12-slim-bookworm

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
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and set permissions
RUN useradd -m appuser && \
    mkdir -p /app/storage && \
    chown -R appuser:appuser /app

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.minimal.txt requirements.txt ./

# Install Python dependencies (handling requirements files separately to avoid conflicts)
RUN pip install --no-cache-dir -r requirements.minimal.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir msgraph-core>=1.0.0 msgraph-sdk>=1.0.0 azure-identity

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