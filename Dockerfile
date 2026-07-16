# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8080

# Environment variables for Python
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the application
# Cloud Run expects the app to listen on the port defined by $PORT
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT}
