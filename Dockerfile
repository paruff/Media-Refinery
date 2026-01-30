# Base image
FROM python:3.14-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies if requirements.txt exists
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Expose input and output directories as volumes
VOLUME ["/input", "/output"]

# Default command to run the Python application
ENTRYPOINT ["python", "src/audio/converter.py", "--input", "/input", "--output", "/output"]
