FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY documentLM/pyproject.toml documentLM/uv.lock documentLM/README.md ./
COPY documentLM/src/ src/
COPY documentLM/static/ static/
COPY nlp_utils/ /nlp_utils/

RUN uv sync --no-dev

CMD ["uv", "run", "uvicorn", "writer.main:app", "--host", "0.0.0.0", "--port", "8000"]
