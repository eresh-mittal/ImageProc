# Use official Python slim image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies that might be needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Install poetry with pip directly
RUN pip install --no-cache-dir poetry

# Copy only pyproject.toml first for dependency caching
COPY pyproject.toml poetry.lock ./

# Configure poetry to create the virtual environment in the project
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-root

# Copy application code
COPY . .

# Create upload and output directories
# RUN mkdir -p uploads outputs

# Expose necessary ports
EXPOSE 5000 6379

# Use a shell script to start all services
CMD ["./entrypoint.sh"]