# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and source code for dependencies
COPY pyproject.toml ./
COPY src ./src

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy the rest of the application code (if any other files needed)
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"] 