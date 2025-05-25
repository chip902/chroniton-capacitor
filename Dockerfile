FROM python:3.11-bullseye

WORKDIR /app

# Install dependencies first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Create a non-root user for better security
RUN adduser --disabled-password --gecos "" appuser
RUN mkdir -p /app/storage && chown -R appuser:appuser /app
USER appuser

# Expose the port the app runs on
EXPOSE 8008

# Use entrypoint script for better debugging and startup
ENTRYPOINT ["/app/entrypoint.sh"]