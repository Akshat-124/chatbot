FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Hugging Face Spaces exposes port 7860 by default
EXPOSE 7860

# Run FastAPI server on port 7860 for Hugging Face Spaces
CMD ["uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "7860"]
