# Use the official Python image from the Docker Hub
FROM mcr.microsoft.com/devcontainers/python:0-3.11

ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt
# RUN pip install --upgrade -r requirements.txt

COPY dashboard/ .
COPY common/ ./common

CMD ["python", "__init__.py"]


########################### DEPRECATED ###########################

# CMD ["gunicorn", "-c", "gunicorn_config.py", "main:app"]

########################### NOTES ###########################

# how I used to run gunicorn manually before I went to microservices

# gunicorn -c gunicorn_config.py main:app