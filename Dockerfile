# Use Python 3.11 alpine image
FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Install system dependencies (Alpine)
RUN apk add --no-cache git

# Copy only files required for dependency installation first
COPY pyproject.toml ./
# Copy application source code before installing dependencies
COPY src/ ./src/
# Install Python dependencies
RUN pip install --no-cache-dir .

# Create non-root user (Alpine)
RUN adduser -D -h /app -s /bin/sh app && \
    chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Healthcheck: run a lightweight CLI command to verify health
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 CMD python src/main.py --version || exit 1

# Default command
ENTRYPOINT ["python", "src/main.py"]
CMD ["--help"] 