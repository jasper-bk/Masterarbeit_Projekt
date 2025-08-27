# --- Base: Python 3.13 ---
FROM python:3.13-slim AS base

# Sytem packages for builds and Jupyter
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of files
COPY . .

# --- Stage for Deployment ---
FROM base AS final

# Port for web app
EXPOSE 8080

CMD ["python3", "-u", "main.py"]