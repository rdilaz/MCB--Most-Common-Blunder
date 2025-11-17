# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Stockfish executable and give it permissions
COPY ./stockfish/stockfish /app/stockfish/stockfish
RUN chmod +x /app/stockfish/stockfish

# Copy the rest of your application's code
COPY . .

# Tell the container to run your app using Gunicorn when it starts
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "2", "--threads", "4", "app:app"]