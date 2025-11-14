# Health Server

The health server provides lightweight HTTP endpoints (via Flask) suitable for container/Kubernetes liveness, readiness and basic service info. Implementation is in [src/hmpps/services/health_server.py](src/hmpps/services/health_server.py) via the [`HealthServer`](src/hmpps/services/health_server.py) class and a helper function [`setup_logging`](src/hmpps/services/health_server.py).

## Endpoints

- `/health`  
  Returns:
  ```
  {
    "status": "UP",
    "service": "<derived-host-name>"
  }
  ```
  HTTP 200 if status == UP else 503 (currently always UP).

- `/info`  
  Returns build + runtime metadata:
  ```
  {
    "build": { "version": "<APP_VERSION or dev>", "name": "<host>" },
    "uptime": <seconds since server thread started>,
    "environment": "<ENVIRONMENT (optional)>",
    "productId": "<PRODUCT_ID (optional)>"
  }
  ```

- `/ping`  
  Returns plain text `pong` (HTTP 200).

- 404 handler returns `Not found.`

## Environment Variables

- `APP_VERSION` – surfaced in `/info` (defaults to `dev`).
- `ENVIRONMENT` – optional, added to `/info`.
- `PRODUCT_ID` – optional, added to `/info`.
- `LOG_LEVEL` – logging level (defaults to INFO).

## Host Name Derivation

`socket.gethostname()` is trimmed: if the hostname has 3+ hyphen‑separated parts, the last two segments are removed (to strip ephemeral suffixes), else the full hostname is used.

## Lifecycle / Threading

Calling [`HealthServer.start`](src/hmpps/services/health_server.py) launches a background (daemon) thread that runs Flask on `0.0.0.0:8080` without debug or reloader. Uptime metrics begin when the thread starts.

Internally:
- [`HealthServer.start`](src/hmpps/services/health_server.py) → spawns thread targeting `start_health_server`.
- [`HealthServer.start_health_server`](src/hmpps/services/health_server.py) → sets `app_start_time`, configures werkzeug logging level, runs the Flask app.

## Logging

`setup_logging(LOG_LEVEL)` configures a simple stream handler. Flask/werkzeug request logs are reduced to WARNING level.

## Usage Example

```py
from hmpps import HealthServer

# Instantiate
health = HealthServer()

# Start background server (default port 8080)
health.start()

# Application continues; endpoints now available:
#   /health
#   /info
#   /ping
```

## Custom Port

The public `.start()` method always uses port 8080. To use a different port:

```py
from hmpps.services.health_server import HealthServer

health = HealthServer()

# Direct invocation (blocks current thread):
health.start_health_server(port=9000)
```

If non‑blocking operation with a custom port is required, wrap `start_health_server` yourself in a thread.

## Caveats

- Not intended as a general web server (only health/info).
- No authentication.
- Uptime resets if the process restarts.
- Changing port requires direct call to `start_health_server`.