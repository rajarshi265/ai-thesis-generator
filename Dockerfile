# Use an official, lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI backend script
COPY main.py .

# Copy the frontend folder into the container as /app/static
COPY static/ ./static/

# Expose port 80 (the default HTTP port)
EXPOSE 80

# Command to run the application using fastapi in exec form
CMD ["fastapi", "run", "main.py", "--port", "80"]