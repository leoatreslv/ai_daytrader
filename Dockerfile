# Base Image
# Use Bullseye to get OpenSSL 1.1.1 for better compatibility with legacy SSL servers
# (Bookworm/Python 3.12 uses OpenSSL 3.0 which is very strict)
FROM python:3.11-slim-bullseye

# Set Working Directory
WORKDIR /app

# Install System Dependencies (Minimal)
# gcc/build-essential might be needed for some python extensions
# ca-certificates and openssl are needed for SSL/TLS connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    openssl \
    git \
    && rm -rf /var/lib/apt/lists/*
    
# Update certificates
RUN update-ca-certificates

# Copy Requirements
COPY requirements.txt .

# Install Dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Application Code
COPY . .

# Set Environment Variables
ENV PYTHONUNBUFFERED=1

# Command to Run
CMD ["python", "main.py"]
