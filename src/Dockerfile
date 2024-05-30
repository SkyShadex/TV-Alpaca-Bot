# Use the official Python image from the Docker Hub
FROM mcr.microsoft.com/devcontainers/python:0-3.11

ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt
# RUN pip install --upgrade -r requirements.txt

COPY src/ .

EXPOSE 5000

CMD ["python", "__init__.py"]

# CMD ["gunicorn", "-c", "gunicorn_config.py", "main:app"]

# gunicorn -c gunicorn_config.py main:app