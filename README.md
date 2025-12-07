#  Webhook API with FastAPI

A production-ready containerized webhook API built with FastAPI, featuring HMAC authentication, idempotency, structured JSON logging, Prometheus metrics, and a real-time dashboard.

##  Features

- **HMAC-SHA256 Security**: Request authentication using X-Signature header
- **Idempotency**: Duplicate message detection using message_id as primary key
- **Structured JSON Logging**: One JSON object per line with ISO-8601 timestamps
- **Prometheus Metrics**: HTTP request tracking and webhook-specific metrics
- **Real-time Dashboard**: Auto-refreshing UI showing messages and statistics
- **Health Checks**: Liveness and readiness probes for Kubernetes
- **Async Database**: SQLAlchemy with async SQLite (aiosqlite)
- **E.164 Validation**: Phone number format validation
- **Docker Support**: Fully containerized with docker-compose

##  Project Structure

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

## 🛠️ How to Run

### Prerequisites

- Docker Desktop installed and running
- Docker Compose (included with Docker Desktop)
- Make (optional, for convenience commands)
- `curl` and `jq` (optional, for testing)

### Quick Start

1. **Start Docker Desktop** (if not already running)

2. **Start the application**:

   ```bash
   make up
   ```

   Or without Make:

   ```bash
   docker compose up -d --build
   ```

   This will:

   - Build the Docker image with all dependencies
   - Start the webhook API container
   - Expose port 8000 on localhost
   - Create a persistent volume for the SQLite database

3. **Verify the application is running**:

   ```bash
   docker ps
   ```

   You should see `webhook-api` container with status "Up" and "healthy"

4. **View logs in real-time**:
   ```bash
   make logs
   ```

### Available URLs

Once started, the following endpoints are available:

- **Dashboard (UI)**: http://localhost:8000/ui
- **API Root**: http://localhost:8000/
- **Webhook Endpoint**: http://localhost:8000/webhook
- **Messages API**: http://localhost:8000/messages
- **Statistics API**: http://localhost:8000/stats
- **Prometheus Metrics**: http://localhost:8000/metrics
- **Health Check (Liveness)**: http://localhost:8000/health/live
- **Health Check (Readiness)**: http://localhost:8000/health/ready

### Stopping the Application

```bash
make down
```

Or:

```bash
docker compose down -v
```

## 📡 How to Hit Endpoints

### Dashboard (Browser)

Simply open in your browser:

```
http://localhost:8000/ui
```

The dashboard auto-refreshes every 5 seconds showing messages and statistics.

### POST /webhook - Send a Message

**Important**: This endpoint requires HMAC-SHA256 authentication.

**Step 1: Compute the HMAC signature**

```bash
SECRET="testsecret"  # Use your WEBHOOK_SECRET from docker-compose.yml
PAYLOAD='{"message_id":"msg_001","from":"+14155552671","to":"+14155552672","ts":"2025-12-07T10:30:00Z","text":"Hello, World!"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')
```

**Step 2: Send the request**

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

**Response**:

- `200 OK {"status": "ok"}` - Success (new or duplicate message)
- `401 Unauthorized {"detail": "invalid signature"}` - Invalid/missing signature
- `422 Unprocessable Entity` - Validation error (e.g., invalid phone format)

**Field Requirements**:

- `message_id`: String, unique identifier
- `from`: E.164 format phone number (e.g., +14155552671)
- `to`: E.164 format phone number
- `ts`: ISO-8601 timestamp string
- `text`: Optional string, max 4096 characters

### GET /messages - List Messages

**Basic request**:

```bash
curl http://localhost:8000/messages | jq
```

**With pagination**:

```bash
# Get first 10 messages
curl "http://localhost:8000/messages?limit=10&offset=0" | jq

# Get next 10 messages
curl "http://localhost:8000/messages?limit=10&offset=10" | jq
```

**With filtering**:

```bash
# Filter by sender (URL encode the + sign as %2B)
curl "http://localhost:8000/messages?from=%2B14155552671" | jq

# Filter by timestamp (messages since a specific time)
curl "http://localhost:8000/messages?since=2025-12-07T10:00:00Z" | jq

# Search text content
curl "http://localhost:8000/messages?q=Hello" | jq

# Combine filters
curl "http://localhost:8000/messages?from=%2B14155552671&since=2025-12-07T10:00:00Z&limit=5" | jq
```

**Response format**:

```json
{
  "data": [
    {
      "message_id": "msg_001",
      "from_msisdn": "+14155552671",
      "to_msisdn": "+14155552672",
      "ts": "2025-12-07T10:30:00Z",
      "text": "Hello, World!",
      "created_at": "2025-12-07T10:30:05Z"
    }
  ],
  "total": 150
}
```

**Ordering**: Results are always ordered by `ts ASC, message_id ASC`

### GET /stats - Get Statistics

```bash
curl http://localhost:8000/stats | jq
```

**Response**:

```json
{
  "total_messages": 150,
  "senders_count": 25,
  "messages_per_sender": [
    { "from_msisdn": "+14155552671", "count": 45 },
    { "from_msisdn": "+14155552672", "count": 32 }
  ],
  "first_message_ts": "2025-12-01T10:30:00Z",
  "last_message_ts": "2025-12-07T15:45:00Z"
}
```

### GET /metrics - Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

**Key metrics**:

- `http_requests_total{path, status}` - Total HTTP requests by endpoint and status
- `webhook_requests_total{result}` - Webhook outcomes: "created", "duplicate", "invalid_signature"

### Health Checks

**Liveness** (is the app running?):

```bash
curl http://localhost:8000/health/live
# Response: {"status": "alive"}
```

**Readiness** (can the app serve traffic?):

```bash
curl http://localhost:8000/health/ready
# Response: {"status": "ready"} or 503 if DB is down
```

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

##  Development

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

##  Design Decisions

### 1. HMAC Verification Implementation

**Why HMAC-SHA256?**

- Industry-standard for webhook authentication (used by GitHub, Stripe, etc.)
- Cryptographically secure message authentication
- Prevents request forgery and replay attacks

**Implementation Details**:

```python
# app/main.py - verify_hmac_signature dependency
async def verify_hmac_signature(request: Request) -> bytes:
    # 1. Extract signature from X-Signature header
    signature_header = request.headers.get("X-Signature")

    # 2. Read raw request body BEFORE Pydantic parsing
    raw_body = await request.body()

    # 3. Compute HMAC-SHA256 using webhook secret
    expected_signature = hmac.new(
        key=settings.WEBHOOK_SECRET.encode('utf-8'),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    # 4. Constant-time comparison (prevents timing attacks)
    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    return raw_body
```

**Key Design Choices**:

1. **Verify Before Parsing**: Signature is verified on raw bytes before Pydantic validation. This prevents attackers from sending malformed payloads that could bypass validation.

2. **Constant-Time Comparison**: Using `hmac.compare_digest()` instead of `==` prevents timing attacks where an attacker could determine the correct signature by measuring response times.

3. **FastAPI Dependency**: Implemented as a dependency so it runs automatically before the endpoint handler, keeping business logic clean.

4. **401 Unauthorized**: Returns 401 (not 403) for invalid signatures, following HTTP spec for authentication failures.

5. **Database Protection**: Invalid signatures fail fast without touching the database, protecting against DoS attacks.

---

### 2. Pagination Contract

**Design Philosophy**: Offset-based pagination with explicit total count for client-side UX.

**Contract**:

```json
{
  "data": [...],      // Array of message objects
  "total": 150        // Total count matching filters
}
```

**Query Parameters**:

- `limit`: Items per page (1-100, default 50)
- `offset`: Number of items to skip (default 0)

**Example Pagination**:

```bash
# Page 1 (items 1-10)
GET /messages?limit=10&offset=0

# Page 2 (items 11-20)
GET /messages?limit=10&offset=10

# Page 3 (items 21-30)
GET /messages?limit=10&offset=20
```

**Why This Design?**

1. **Simple Mental Model**: Offset-based pagination is intuitive - "skip N, take M"

2. **Client Control**: Client can request any page size (within limits) and jump to any page

3. **Total Count**: Returning `total` allows clients to:

   - Calculate total pages: `Math.ceil(total / limit)`
   - Show "Showing 1-10 of 150 results"
   - Enable/disable next/previous buttons

4. **Filter Awareness**: `total` respects filters, so filtered results show correct counts

5. **Predictable Ordering**: Always `ORDER BY ts ASC, message_id ASC` ensures:
   - Consistent pagination across requests
   - Chronological message display
   - Tie-breaking with message_id for same timestamps

**Trade-offs**:

- ✅ Simple to implement and use
- ✅ Can jump to any page
- ❌ Performance degrades with large offsets (deep pagination)
- ❌ Results can shift if data changes during pagination

**Alternative Considered**: Cursor-based pagination would solve the shifting results problem but adds complexity and doesn't allow jumping to arbitrary pages. For this use case (webhook messages with finite growth), offset-based is simpler and sufficient.

---

### 3. /stats Endpoint Definition

**Design Goal**: Provide actionable insights about message traffic in a single request.

**Response Schema**:

```json
{
  "total_messages": 150, // Total count of all messages
  "senders_count": 25, // Unique sender count
  "messages_per_sender": [
    // Top 10 senders by volume
    {
      "from_msisdn": "+14155552671",
      "count": 45
    }
  ],
  "first_message_ts": "2025-12-01T10:30:00Z", // Earliest message
  "last_message_ts": "2025-12-07T15:45:00Z" // Latest message
}
```

**Why These Metrics?**

1. **total_messages**: Basic health metric - shows system activity level

2. **senders_count**: Indicates sender diversity

   - High count = many unique users
   - Low count = concentrated traffic (potential abuse)

3. **messages_per_sender (Top 10)**:

   - **Why top 10?** Balances detail vs. response size
   - **Ordered by count DESC**: Shows highest volume senders first
   - **Use cases**:
     - Identify power users
     - Detect spam/abuse (one sender sending too much)
     - Business intelligence (which customers are most active)
   - **Why senders not recipients?** Senders initiate messages, more relevant for rate limiting

4. **first_message_ts / last_message_ts**:
   - Shows message time range
   - Useful for monitoring (when did messages start/stop flowing?)
   - Helps identify data freshness

**Implementation Details**:

```python
# Efficient SQL queries using aggregation
total_messages = await db.execute(
    select(func.count(Message.message_id))
)

senders_count = await db.execute(
    select(func.count(func.distinct(Message.from_msisdn)))
)

# Top 10 with GROUP BY and ORDER BY
messages_per_sender = await db.execute(
    select(Message.from_msisdn, func.count(Message.message_id))
    .group_by(Message.from_msisdn)
    .order_by(func.count(Message.message_id).desc())
    .limit(10)
)
```

**Why Not Include**:

- ❌ **recipients_count**: Less actionable than senders
- ❌ **Average message length**: Text is optional, would need null handling
- ❌ **Messages per hour/day**: Requires time bucketing, adds complexity

---

### 4. Prometheus Metrics Design

**Metrics Exposed**:

```python
# Counter: HTTP requests by endpoint and status
http_requests_total{path="/messages", status="200"}

# Counter: Webhook outcomes by result type
webhook_requests_total{result="created"}       # New message inserted
webhook_requests_total{result="duplicate"}     # Idempotency - already exists
webhook_requests_total{result="invalid_signature"}  # Security - rejected
```

**Why These Metrics?**

1. **http_requests_total**:

   - Standard RED metric (Rate, Errors, Duration)
   - Labels: `path` (endpoint), `status` (HTTP status code)
   - **Use cases**:
     - Alert on high 4xx/5xx rates
     - Track endpoint usage
     - Capacity planning

2. **webhook_requests_total with result labels**:

   - **result="created"**: Success rate - new messages processed
   - **result="duplicate"**: Idempotency rate - how many retries/duplicates
   - **result="invalid_signature"**: Security metric - attempted attacks

   **Insights**:

   - High `created`: Healthy traffic
   - High `duplicate`: Client retry issues or replay attacks
   - High `invalid_signature`: Possible attack or misconfiguration

**Implementation Pattern**:

```python
# Track in webhook endpoint after outcome is determined
try:
    await save_message(db, message_data)
    webhook_requests_total.labels(result='created').inc()
except IntegrityError:
    webhook_requests_total.labels(result='duplicate').inc()

# Track in HMAC validator on failure
if not hmac.compare_digest(signature_header, expected_signature):
    webhook_requests_total.labels(result='invalid_signature').inc()
    raise HTTPException(...)
```

**Why Counters?**

- Monotonically increasing
- Prometheus can calculate rates: `rate(webhook_requests_total[5m])`
- Can alert on anomalies: "if invalid_signature rate > threshold"

**Design Principles**:

- ✅ **Cardinality Control**: Limited label values (3 for result) prevents metric explosion
- ✅ **Business Metrics**: Beyond infrastructure, track application-level outcomes
- ✅ **Actionable**: Each metric can drive alerts or dashboards

---

### 5. Additional Key Decisions

**Idempotency via PRIMARY KEY**:

- `message_id` is the PRIMARY KEY (not auto-increment ID)
- Database enforces uniqueness at the constraint level
- Duplicate inserts raise `IntegrityError`, caught and handled gracefully
- Returns 200 OK for duplicates (idempotent behavior)
- Logged with `dup: true` for observability

**Async Database**:

- SQLAlchemy with `asyncio` and `aiosqlite`
- Non-blocking I/O allows handling concurrent requests
- Better resource utilization than synchronous code

**Structured Logging**:

- JSON logs (one per line) for machine parsing
- Fields: `ts`, `level`, `request_id`, `method`, `path`, `status`, `latency_ms`, `dup`
- `ContextVar` tracks request_id across async operations
- Easy to ingest into log aggregation systems (ELK, Splunk, etc.)

**E.164 Phone Validation**:

- Regex: `^\+[1-9]\d{1,14}$`
- Enforces international format
- Prevents invalid phone numbers at API boundary

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Acknowledgments

Built with:

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database toolkit
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Prometheus Client](https://github.com/prometheus/client_python) - Metrics
- [Uvicorn](https://www.uvicorn.org/) - ASGI server


USED VS CODE WITH GIHUB COPILOT CLAUDE SONNET 4.5 EXTENSIVELY FOR THIS PROJECT WHILE GETTING THE BASIC ROADMAP AND PROMPT ENGINEERING THROUGH GOOGLE GEMINI 3.0 PRO