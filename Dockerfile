# Backend image for the Tokenised Fund Servicing Platform API.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY contracts ./contracts
COPY deployments ./deployments

WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "app"]
