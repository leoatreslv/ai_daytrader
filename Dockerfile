# Base Image
FROM python:3.12-slim

# Set Working Directory
WORKDIR /app

# Install System Dependencies (Minimal)
# gcc/build-essential might be needed for some python extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

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
