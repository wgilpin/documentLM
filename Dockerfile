FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
COPY src/ src/

RUN uv sync --no-dev

CMD ["uv", "run", "uvicorn", "writer.main:app", "--host", "0.0.0.0", "--port", "8000"]
