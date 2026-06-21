FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
RUN pip install --no-cache-dir .

CMD ["uvicorn", "telepa3on.app:app", "--host", "0.0.0.0", "--port", "8000"]
