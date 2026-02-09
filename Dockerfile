# Base Image: Python 3.11 Slim (Bullseye for OpenSSL 1.1 compatibility)
FROM python:3.11-slim-bullseye

# Set Working Directory
WORKDIR /app

# 1. System Dependencies
# - git: for installing from GitHub URLs
# - build-essential: for compiling extensions (if needed fallback)
# - ca-certificates/openssl: for secure connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    ca-certificates \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Update CA Certificates to ensure SSL works
RUN update-ca-certificates

# 2. Upgrade Python Build Tools
# Essential for modern pip/setuptools behavior and avoiding pkg_resources errors
RUN pip install --no-cache-dir --upgrade pip setuptools wheel setuptools-scm

# 3. Heavy Dependencies (Force Binary)
# Install numpy and pandas specifically as binaries to avoid source compilation
# This prevents the "Building wheel for pandas failed" error
RUN pip install --no-cache-dir --only-binary=:all: "numpy<2.0.0" "pandas<3.0.0"

# 4. Install pandas-ta (The Tricky Part)
# - Install from GitHub development branch (standard release is missing/broken on PyPI)
# - Use --no-build-isolation to force it to use the pre-installed numpy/pandas
RUN pip install --no-cache-dir --no-build-isolation "pandas_ta @ https://github.com/twopirllc/pandas-ta/archive/development.zip"

# 5. Runtime Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy Application Code
COPY . .

# Environment Config
ENV PYTHONUNBUFFERED=1

# Run
CMD ["python", "main.py"]
