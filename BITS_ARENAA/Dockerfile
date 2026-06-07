FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
# Install system dependencies (build-essential, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
# Copy the rest of the application code
COPY . /app/
# Expose Django's default port
EXPOSE 8000
# Start the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]