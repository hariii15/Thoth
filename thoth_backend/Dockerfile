# Use the official Python image as the base image
FROM python:3.10-slim

# Prevent Python from writing pyc files / buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Set the working directory in the container
WORKDIR /app

# Copy only requirements first for better layer caching
COPY requirements.txt ./

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the application runs on (if applicable)
EXPOSE 8000

# Set the default command to run the application
CMD ["bash", "-c", "gunicorn main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:${PORT}"]