FROM python:3.11-bullseye

# Create app directory and set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Create a non-root user and set permissions
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/storage \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8008

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]