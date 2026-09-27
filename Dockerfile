FROM python:3.12-slim

RUN pip install --no-cache-dir requests google-auth

RUN useradd --create-home app
USER app
WORKDIR /app
COPY gemini_rpd.py .

ENTRYPOINT ["python", "gemini_rpd.py"]
