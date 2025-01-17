# Stage 1: Build stage
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install FFmpeg and other necessary dependencies in one layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libffi-dev \
    libssl-dev \
    ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional necessary packages (e.g., uvicorn for development)
RUN pip install uvicorn python-multipart starlette


# Copy the application code into the container
COPY . .

# Expose the port the app will run on
EXPOSE 8000

# Command to run the FastAPI app in development mode with auto-reloading
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
