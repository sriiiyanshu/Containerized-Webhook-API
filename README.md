# 📬 Webhook API with FastAPI

A production-ready containerized webhook API built with FastAPI, featuring HMAC authentication, idempotency, structured JSON logging, Prometheus metrics, and a real-time dashboard.

## 🚀 Features

- **HMAC-SHA256 Security**: Request authentication using X-Signature header
- **Idempotency**: Duplicate message detection using message_id as primary key
- **Structured JSON Logging**: One JSON object per line with ISO-8601 timestamps
- **Prometheus Metrics**: HTTP request tracking and webhook-specific metrics
- **Real-time Dashboard**: Auto-refreshing UI showing messages and statistics
- **Health Checks**: Liveness and readiness probes for Kubernetes
- **Async Database**: SQLAlchemy with async SQLite (aiosqlite)
- **E.164 Validation**: Phone number format validation
- **Docker Support**: Fully containerized with docker-compose

## 📁 Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and endpoints
│   ├── models.py            # Pydantic models for validation
│   ├── storage.py           # SQLAlchemy async database layer
│   ├── config.py            # Configuration with pydantic-settings
│   ├── logging_utils.py     # Structured JSON logging
│   ├── metrics.py           # Prometheus metrics (future)
│   └── tests/
│       ├── test_webhook.py
│       ├── test_messages.py
│       └── test_stats.py
├── static/
│   └── index.html           # Dashboard UI
├── data/                    # SQLite database (created at runtime)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── README.md
```

## 🛠️ Setup

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

### Quick Start

1. **Clone the repository** (or use the existing project)

2. **Start the application**:

   ```bash
   make up
   # or
   docker compose up -d --build
   ```

3. **View logs**:

   ```bash
   make logs
   # or
   docker compose logs -f api
   ```

4. **Access the dashboard**:
   Open http://localhost:8000/ui in your browser

## 📡 API Endpoints

### POST /webhook

Receive webhook messages with HMAC authentication.

**Headers**:

- `X-Signature`: HMAC-SHA256 hex digest of request body

**Request Body**:

```json
{
  "message_id": "msg_123456",
  "from": "+14155552671",
  "to": "+14155552672",
  "ts": "2025-12-07T10:30:00Z",
  "text": "Hello, World!"
}
```

**Response**: `200 OK {"status": "ok"}`

### GET /messages

Retrieve messages with filtering and pagination.

**Query Parameters**:

- `limit` (1-100, default 50): Number of messages
- `offset` (default 0): Pagination offset
- `from`: Filter by sender phone number
- `since`: Filter messages with ts >= since
- `q`: Search in message text

**Response**:

```json
{
  "data": [...],
  "total": 150
}
```

### GET /stats

Get aggregate statistics.

**Response**:

```json
{
  "total_messages": 150,
  "senders_count": 25,
  "messages_per_sender": [{ "from_msisdn": "+14155552671", "count": 45 }],
  "first_message_ts": "2025-12-01T10:30:00Z",
  "last_message_ts": "2025-12-07T15:45:00Z"
}
```

### GET /metrics

Prometheus metrics endpoint.

**Metrics**:

- `http_requests_total{path, status}`: Total HTTP requests
- `webhook_requests_total{result}`: Webhook requests by result (created/duplicate/invalid_signature)

### Health Checks

- `GET /health/live`: Liveness probe (always returns 200)
- `GET /health/ready`: Readiness probe (checks DB connection)
- `GET /health`: Legacy health check

## 🔐 Environment Variables

- **`WEBHOOK_SECRET`** (required): Secret key for HMAC authentication
- **`DATABASE_URL`** (default: `sqlite+aiosqlite:///./data/app.db`): Database connection string
- **`LOG_LEVEL`** (default: `INFO`): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## 🧪 Testing

Run tests inside the container:

```bash
make test
# or
docker compose run --rm api pytest
```

## 📊 Monitoring

### Logs

Structured JSON logs with fields:

- `ts`: ISO-8601 timestamp
- `level`: Log level
- `request_id`: Unique request identifier
- `method`, `path`, `status`, `latency_ms`: HTTP request details
- `dup`: Idempotency flag for webhook requests

View logs:

```bash
make logs
```

### Metrics

Access Prometheus metrics:

```bash
make metrics
# or
curl http://localhost:8000/metrics
```

### Dashboard

Real-time dashboard at http://localhost:8000/ui

- Auto-refreshes every 5 seconds
- Shows recent messages
- Displays statistics and top senders

## 🐳 Docker Commands

```bash
# Start the application
make up

# Stop and remove containers
make down

# View logs
make logs

# Run tests
make test

# Restart the application
make restart

# Open shell in container
make shell

# Clean everything
make clean

# Check health
make health
```

## 🔧 Development

### Local Development (without Docker)

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**:

   ```bash
   export WEBHOOK_SECRET=mysecret123
   export DATABASE_URL=sqlite+aiosqlite:///./data/app.db
   export LOG_LEVEL=INFO
   ```

3. **Create data directory**:

   ```bash
   mkdir -p data
   ```

4. **Run the application**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Testing Webhook Endpoint

```bash
# Generate HMAC signature
SECRET="mysecret123"
PAYLOAD='{"message_id":"msg_123","from":"+14155552671","to":"+14155552672","ts":"2025-12-07T10:30:00Z","text":"Hello"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

# Send webhook request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

## 📝 Architecture Decisions

### Idempotency

- Uses `message_id` as PRIMARY KEY in database
- Duplicate requests return 200 OK without inserting
- Prevents duplicate processing of the same message

### Security

- HMAC-SHA256 signature verification before payload parsing
- Constant-time comparison to prevent timing attacks
- 401 Unauthorized for invalid/missing signatures

### Logging

- Structured JSON format for easy parsing
- Request IDs tracked across async operations using ContextVar
- HTTP request/response logging in middleware

### Database

- Async SQLAlchemy with aiosqlite
- Database persisted in Docker volume
- Automatic table creation on startup

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

Built with:

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database toolkit
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Prometheus Client](https://github.com/prometheus/client_python) - Metrics
- [Uvicorn](https://www.uvicorn.org/) - ASGI server
