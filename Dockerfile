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

# Run Streamlit on port 7860
ENTRYPOINT ["streamlit", "run", "streamlit_rag_frontend.py", "--server.port=7860", "--server.address=0.0.0.0"]
