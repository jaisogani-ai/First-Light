# First Light — single lightweight container running the FastAPI backend + static dashboard.
# No Kubernetes/microservices/Postgres — SQLite lives on a mounted volume for persistence.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FIRST_LIGHT_DATABASE_URL=sqlite:////data/first_light.db
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
