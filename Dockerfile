FROM python:3.11-slim

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Create and set the working directory
WORKDIR /app

# Copy the entire backend directory into the container
COPY backend /app/backend

# Change into the backend directory
WORKDIR /app/backend

# Install the application dependencies
RUN pip install --no-cache-dir -e .

# Expose the port Railway provides (Railway sets PORT automatically, but we document 8000)
EXPOSE 8000

# Start the FastAPI application using Uvicorn
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
