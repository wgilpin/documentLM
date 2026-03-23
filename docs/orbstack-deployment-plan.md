# Deployment Guide: documentLM on OrbStack

## 1. Cloudflare Tunnel Setup

* Log in to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/).
* Navigate to **Networks** > **Tunnels**.
* Select **Add a Tunnel** > **Cloudflared**.
* Name the tunnel (e.g., `mac-mini-prod`).
* Select **Docker** as the environment.
* Copy the token string provided in the command (the string immediately following `--token`).

## 2. Prepare Configuration Files

Ensure these files are in `/Users/will/projects/documentLM/`.

### Dockerfile

* Implements a non-root user.
* Secures the working directory.

```dockerfile
FROM python:3.13-slim
RUN useradd -m appuser
WORKDIR /home/appuser/app
RUN pip install uv
COPY pyproject.toml uv.lock* ./
RUN chown -R appuser:appuser /home/appuser/app
USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
COPY --chown=appuser:appuser src/ src/
RUN uv sync --no-dev
CMD ["uv", "run", "uvicorn", "writer.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

* Isolates the database on an internal-only network.
* Uses the Cloudflare Tunnel for all ingress traffic.

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME:-writer}
      POSTGRES_USER: ${DB_USER:-writer}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - backend

  app:
    build: .
    depends_on:
      - postgres
    env_file: .env
    volumes:
      - ./data/chroma:/home/appuser/app/data/chroma
    networks:
      - frontend
      - backend

  tunnel:
    image: cloudflare/cloudflared:latest
    restart: always
    command: tunnel --no-autoupdate run --token ${CF_TUNNEL_TOKEN}
    networks:
      - frontend

networks:
  frontend:
  backend:
    internal: true

volumes:
  postgres_data:
```

### .env

* Store secrets and tokens.

```text
DB_PASSWORD=your_secure_password
CF_TUNNEL_TOKEN=your_token_from_step_1
```

## 3. Deployment

* Open Terminal in the project directory.
* Execute: `docker compose up -d --build`.
* Verify status in the OrbStack GUI.

## 4. Public Hostname Mapping

* In Cloudflare Tunnel dashboard: **Edit Tunnel** > **Public Hostname**.
* **Subdomain:** `app`
* **Domain:** `teleosis.ai`
* **Service Type:** `HTTP`
* **URL:** `app:8000`
* Save to activate `https://app.teleosis.ai`.

## 5. Local Development Access

To bypass the tunnel for local debugging, create `docker-compose.dev.yml`:

```yaml
services:
  postgres:
    ports: ["5432:5432"]
  app:
    ports: ["8000:8000"]
```

Run with: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`.
