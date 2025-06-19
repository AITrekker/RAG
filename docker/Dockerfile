# Stage 1: Builder
# Use the development image with build tools
FROM nvidia/cuda:11.8-devel-ubuntu22.04 AS builder

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies needed for building wheels
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    libblas3 \
    liblapack3 \
    liblapack-dev \
    libblas-dev \
    gfortran \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better caching
WORKDIR /app
COPY docker/requirements.docker.txt requirements.txt

# Install Python dependencies into the virtual environment
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Final Image
# Use a smaller base image for the final application
FROM nvidia/cuda:11.8-base-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install only necessary runtime system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Make the virtual environment's Python the default
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code and entrypoint
COPY src/ ./src/
COPY docker/entrypoint.sh ./entrypoint.sh

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Create directories for data persistence
RUN mkdir -p /app/data/master /app/data/sync /app/data/logs /app/data/db

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"] 