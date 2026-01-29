# FlaskStat

A lightweight system monitoring dashboard with real-time CPU, memory, disk, and process metrics.

## Features

- Real-time system stats (CPU, memory, disk usage)
- Top 10 processes by memory consumption
- OIDC authentication
- Live updates every 2 seconds
- Mobile responsive UI
- Secure container deployment

## Quick Start

```bash
docker-compose up --build
```

## Example Compose

```compose.yml
services:
  monitor:
    build: .
    container_name: flaskstat
    ports:
      - "84:8080"
    environment:
      - OIDC_PROVIDER_NAME=e.g. Authelia or Pocket ID
      - OIDC_CLIENT_ID=abc123
      - OIDC_CLIENT_SECRET=abc123
      - OIDC_SERVER_METADATA_URL=https://auth.example.com/.well-known/openid-configuration
      - SECRET_KEY= Generate (32bit is fine)
    volumes:
      - /proc:/host/proc:ro
      - /:/host/root:ro
    read_only: true