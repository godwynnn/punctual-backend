# Use an official Python runtime as a parent image
FROM python:3.12.1

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Copy the project code into the container
COPY . /app/

# Optional: If you had Django steps in your build.sh, uncomment these:
# RUN python manage.py collectstatic --no-input

# Start the application using Render's assigned port variable
CMD ["sh", "-c", "gunicorn puntua_backend.wsgi:application --bind 0.0.0.0:$PORT"]
