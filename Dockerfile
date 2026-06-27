# Use an official lightweight Python runtime as a parent image
FROM python:3.9-slim

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Install system dependencies, including Stockfish and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend codebase into the container
COPY . .

# Set permissions and switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Set production environment variable
ENV FLASK_ENV=production

# Expose port 5000 for the Flask server
EXPOSE 5000

# Command to run the application
# Best practice is to use gunicorn, but we'll stick to python app.py as requested for the startup logic
CMD ["python", "app.py"]