# RobComp-PC – Real-Time Data Pipeline

A complete real‑time data pipeline that ingests market data from a WebSocket feed, processes it through Redis Pub/Sub, stores it in MySQL, and exposes it via a **Django** web application (human‑readable) and a **FastAPI** API (machine‑readable). The entire stack is containerised with Docker Compose for easy local deployment.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [Services & Access](#services--access)
- [Implementation Details](#implementation-details)
- [Deviations & Rationale](#deviations--rationale)
- [Bonus Features](#bonus-features)
- [Testing the System](#testing-the-system)

---

## Overview

This project implements a simple real‑time data pipeline that:

- Connects to a public WebSocket feed (Lightstreamer)
- Processes market data messages
- Publishes them to a Redis Pub/Sub channel
- Consumes and stores them in a MySQL database (`RTDS` table) using transactions
- Serves the data via:
  - **Django** – a user‑friendly web interface for registration, login, and profile management
  - **FastAPI** – a machine‑readable REST API with four protected endpoints

All components are orchestrated with **Docker Compose** and can be started with a single command.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | **Python 3.12.3** |
| Containerisation | **Docker** & **Docker Compose** |
| Message Broker | **Redis 7** (alpine) – Pub/Sub |
| Database | **MySQL 8.4** |
| WebSocket Client | `websockets` (async) |
| Async Framework | `asyncio`, `aioredis`, `aiomysql` |
| ORM | **SQLAlchemy 2.0.52** (async) |
| MySQL Driver | **PyMySQL 1.2.0** |
| Web Framework (UI) | **Django 6.1** with custom user model |
| Web Framework (API) | **FastAPI** with OpenAPI/Swagger |
| Reverse Proxy | **Nginx** (alpine) |
| WSGI Server | **Gunicorn** |
| ASGI Server | **Uvicorn** |

---

## Environment Variables

All sensitive configuration is stored in a `.env` file at the project root.

```ini
# Application
APP_ENV=development
REDIS_CHANNEL=RobComp-PC-X


# Redis
REDIS_HOST=redis              
REDIS_PORT=6379            
REDIS_PASSWORD=RobCompPCXPass
REDIS_CHANNEL=RobComp-PC-X

# MySQL
MYSQL_HOST=mysql              
MYSQL_PORT=3306             
MYSQL_DATABASE=RobComp-PC-X
MYSQL_USER=RobComp-PC-X-USER
MYSQL_PASSWORD=RobCompPCXPass
MYSQL_ROOT_PASSWORD=RobCompPCXPass

# FastAPI
FASTAPI_API_KEY=4dbf5a2525252fbbe19285692bbd7e3e # I used  <openssl rand -hex 16> for generating this Secret-key
FASTAPI_API_KEY_HEADER=X-API-Key

# Django
DJANGO_SECRET_KEY=RobComp-PC-django-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,django,nginx

# Nginx
NGINX_PORT=80

USE_MOCK=True
DJANGO_DEBUG=True
```

> **Note on ports:** The Docker containers expose their internal ports to the host. Redis is accessible on host port `6204`, MySQL on `6206`. Inside the container network, services use the internal ports (`6379` for Redis, `3306` for MySQL) via service names (`redis`, `mysql`).

---

## Running the Application

### Prerequisites

- Docker (v20.10+) and Docker Compose (v2+)

### Steps

1. **Start all services with Docker Compose:**
   ```bash
      docker-compose up -d --build
   ```
2. **Create a Django superuser** to access the admin panel:
   ```bash
      docker-compose exec django python manage.py createsuperuser
   ```
3. **Access the application:**
   - Django web app: [http://localhost/app/](http://localhost/app/)
   - Django admin: [http://localhost/app/admin/](http://localhost/app/admin/)
   - FastAPI Swagger docs: [http://localhost/docs](http://localhost/docs)
4. **Check logs:**
   ```bash
      docker-compose logs -f worker_a
      docker-compose logs -f worker_b
      docker-compose logs -f django
      docker-compose logs -f fastapi
   ```

---

## Services & Access

### Nginx (Reverse Proxy)

Nginx acts as the entry point for all HTTP traffic. It listens on port `80` (or `NGINX_PORT` from `.env`) and routes requests to the appropriate backend:

- `/app/` – routes to Django (port 6280) for the human‑readable web interface
- `/api/` – routes to FastAPI (port 6288) for machine‑readable API endpoints
- `/docs` and `/openapi.json` – routed to FastAPI for Swagger documentation
- `/static/` and `/media/` – served directly by Nginx from shared volumes for better performance

This setup ensures clean URL separation between the web app and the API, while Nginx efficiently serves static and media files.

---

### Django Web App

| URL | Description |
|-----|-------------|
| `http://localhost/app/` | Base URL |
| `/app/register/` | Create a new user |
| `/app/login/` | Log in to your account |
| `/app/profile/` | View/edit your own profile |
| `/app/admin/` | Django admin panel (superuser only) |

Django uses a custom `User` model with a one‑to‑one `UserProfile` containing `photo` and `bio`.

---

### FastAPI API

| URL | Description |
|-----|-------------|
| `http://localhost/api/` | Base URL |
| `http://localhost/docs` | Swagger UI – interactive documentation |

**All endpoints** require the static API key passed in the `X-API-Key` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users/get/profile/{userid}` | GET | Returns user profile (excludes credentials and photo) |
| `/users/get/photo/{userid}` | GET | Returns the user's profile photo as Base64 |
| `/RTDS/get/current/{id}` | GET | Returns the most recent market data for instrument `{id}` |
| `/RTDS/get/historical/{id}` | GET | Returns all market data records for instrument `{id}` |

**Example** `curl` **request:**

```bash
curl -H "X-API-Key: 4dbf5a2525252fbbe19285692bbd7e3e" http://localhost/api/users/get/profile/1
```

---

## Implementation Details

### Data Pipeline

The pipeline is event‑driven and fully asynchronous. Worker A and Worker B run as separate long‑lived processes inside Docker containers. They communicate via Redis Pub/Sub, which provides a simple, low‑latency message bus.

**Data Flow:**

```
WebSocket → Worker A → Redis Pub/Sub → Worker B → MySQL → Django / FastAPI
```

Worker B uses a buffered write pattern to batch inserts into MySQL, reducing database load and improving throughput. All writes are performed within a transaction to guarantee data integrity – if any record fails, the entire batch is rolled back and re‑queued.

---

### Worker A (WebSocket → Redis)

- Connects to the Lightstreamer WebSocket (`wss://push2v7.etadbir.com/lightstreamer`)
- Subscribes to 10 assets: AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD, SPY, QQQ
- Parses incoming messages and normalises them into a consistent JSON structure
- Publishes the JSON to the Redis channel `RobComp-PD-X`
- Implements reconnection logic with exponential backoff
- If `USE_MOCK=true` is set, generates simulated price updates instead of using the real WebSocket

---

### Worker B (Redis → MySQL)

- Subscribes to the Redis channel using `aioredis`
- Receives JSON messages and maps them to the `RTDS` schema
- Buffers records in memory; when the buffer reaches `BATCH_SIZE`  or the `FLUSH_INTERVAL`  elapses, it writes the batch to MySQL
- Each batch is written inside a transaction – if any record fails, the entire batch is rolled back and re‑queued
- Uses SQLAlchemy 2.0 with the `aiomysql` driver for asynchronous database operations
- Reconnects to Redis automatically if the connection is lost

---

### Django

- Uses Django's robust authentication system and admin interface
- Extended `AbstractUser` to add a `UserProfile` model with `photo` and `bio`
- Forms handle registration, profile updates, and photo management
- Admin interface inlines `UserProfile` within `UserAdmin`, allowing administrators to edit all user fields
- Media files are stored in a Docker volume (`media_data`) shared with Nginx and FastAPI

---

### FastAPI

- Built for performance and automatic OpenAPI documentation
- Endpoints are protected by a static API key read from `.env`
- Uses SQLAlchemy reflected models to query the same database as Django
- Profile endpoint excludes credentials and photo (photo served separately as Base64)
- Photo endpoint reads the image file from the shared `media` volume and returns it encoded in Base64
- Market data endpoints query the `RTDS` table – `current` returns the most recent record, `historical` returns all records

---

## Bonus Features

| Bonus | Implementation |
|-------|----------------|
| **Asynchronous Implementation** | All workers and FastAPI are fully async |
| **Graceful Connection Handling** | Both workers implement reconnection logic with backoff; Worker B buffers and retries on errors |
| **Logging and Observability** | Every component logs to stdout with structured timestamps |
| **FastAPI Swagger Documentation** | Available at `/docs` with interactive API key authorisation |
| **Docker Support** | Fully containerised with healthchecks and dependencies |

---

## Testing the System

### 1. Verify All Services Are Running

```bash
docker-compose ps
```

### 2. Test Django Web App

1. Register a new user: `http://localhost/app/register/`
2. Log in: `http://localhost/app/login/`
3. Upload a photo and update bio on the profile page
4. Create a superuser and log in to admin: `http://localhost/app/admin/`

### 3. Test FastAPI Endpoints

```bash
curl -H "X-API-Key: 4dbf5a2525252fbbe19285692bbd7e3e" http://localhost/api/users/get/profile/1
curl -H "X-API-Key: 4dbf5a2525252fbbe19285692bbd7e3e" http://localhost/api/users/get/photo/1
curl -H "X-API-Key: 4dbf5a2525252fbbe19285692bbd7e3e" http://localhost/api/RTDS/get/current/AAPL
curl -H "X-API-Key: 4dbf5a2525252fbbe19285692bbd7e3e" http://localhost/api/RTDS/get/historical/AAPL
```

### 4. Test Swagger Documentation

Open `http://localhost/docs` in your browser, click **"Authorize"**, enter your API key, and test endpoints interactively.

### 5. Verify Data Pipeline

```bash
docker-compose logs worker_a   
docker-compose logs worker_b   
```

**Submitted by:** AmirHosseinShamsi  
**GitHub Repository:** [RobComp-PC](https://github.com/Amir-Hossein-shamsi/RobComp-PC)  
**Date:** August 2026