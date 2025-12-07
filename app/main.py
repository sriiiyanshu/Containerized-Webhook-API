"""
FastAPI application for webhook processing with HMAC security and idempotency.
"""

import hmac
import hashlib
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import FastAPI, Request, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select, func, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import WebhookPayload, MessageResponse, StatsResponse
from app.storage import (
    init_db, 
    close_db, 
    get_db, 
    save_message, 
    Message,
    engine,
)
from app.logging_utils import setup_logging, log_request_middleware, get_logger


# Initialize logger
logger = get_logger(__name__)


# ============================================================================
# Prometheus Metrics
# ============================================================================

# HTTP requests counter with path and status labels
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['path', 'status']
)

# Webhook requests counter with result label
webhook_requests_total = Counter(
    'webhook_requests_total',
    'Total webhook requests',
    ['result']  # result can be: 'created', 'duplicate', 'invalid_signature'
)


# ============================================================================
# HMAC Security Dependency
# ============================================================================

async def verify_hmac_signature(request: Request) -> bytes:
    """
    Dependency that validates HMAC signature before processing webhook.
    
    Reads the raw request body and validates the X-Signature header
    using HMAC-SHA256 with the configured webhook secret.
    
    Args:
        request: FastAPI Request object
    
    Returns:
        bytes: Raw request body if signature is valid
    
    Raises:
        HTTPException: 401 if signature is missing or invalid
    """
    # Get the signature from headers
    signature_header = request.headers.get("X-Signature")
    
    if not signature_header:
        logger.warning(
            "Missing X-Signature header",
            extra={"extra_data": {"error": "missing_signature"}}
        )
        # Track invalid signature metric
        webhook_requests_total.labels(result='invalid_signature').inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature"
        )
    
    # Read raw request body
    raw_body = await request.body()
    
    # Compute HMAC-SHA256
    expected_signature = hmac.new(
        key=settings.WEBHOOK_SECRET.encode('utf-8'),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Compare signatures using constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature_header, expected_signature):
        logger.warning(
            "Invalid X-Signature header",
            extra={
                "extra_data": {
                    "error": "invalid_signature",
                    "received": signature_header[:16] + "...",  # Log only prefix
                }
            }
        )
        # Track invalid signature metric
        webhook_requests_total.labels(result='invalid_signature').inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature"
        )
    
    logger.debug("HMAC signature verified successfully")
    return raw_body


# ============================================================================
# Application Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    Startup:
        - Initialize logging
        - Initialize database and create tables
    
    Shutdown:
        - Close database connections
    """
    # Startup
    logger.info("Application starting up...")
    setup_logging(settings.LOG_LEVEL)
    await init_db()
    logger.info("Database initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")
    await close_db()
    logger.info("Database connections closed")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Webhook API",
    description="FastAPI webhook receiver with HMAC security and idempotency",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files (dashboard UI)
app.mount("/ui", StaticFiles(directory="static", html=True), name="static")

# Add request logging middleware
app.middleware("http")(log_request_middleware)


# ============================================================================
# Webhook Endpoint
# ============================================================================

@app.post("/webhook", status_code=200)
async def receive_webhook(
    request: Request,
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    _: bytes = Depends(verify_hmac_signature),
) -> JSONResponse:
    """
    Receive and process webhook messages with HMAC authentication.
    
    Security:
        - Validates HMAC-SHA256 signature in X-Signature header
        - Returns 401 if signature is missing or invalid
    
    Idempotency:
        - Uses message_id as PRIMARY KEY in database
        - Duplicate messages return 200 OK without inserting
        - Logs whether message was created or duplicate
    
    Args:
        request: FastAPI Request object
        payload: Validated webhook payload (WebhookPayload model)
        db: Database session (injected dependency)
        _: Raw body bytes (validates signature, unused after validation)
    
    Returns:
        JSONResponse: {"status": "ok"} with 200 status code
    
    Raises:
        HTTPException: 401 if signature validation fails
    """
    # Convert Pydantic model to dict for database insertion
    message_data = {
        "message_id": payload.message_id,
        "from_msisdn": payload.from_msisdn,
        "to_msisdn": payload.to_msisdn,
        "ts": payload.ts,
        "text": payload.text,
    }
    
    try:
        # Attempt to save message to database
        await save_message(db, message_data)
        await db.commit()
        
        # Track successful creation metric
        webhook_requests_total.labels(result='created').inc()
        
        # Log successful creation
        logger.info(
            f"Message created: {payload.message_id}",
            extra={
                "extra_data": {
                    "message_id": payload.message_id,
                    "from": payload.from_msisdn,
                    "to": payload.to_msisdn,
                    "dup": False,
                }
            }
        )
        
        return JSONResponse(
            status_code=200,
            content={"status": "ok"}
        )
    
    except IntegrityError as e:
        # Duplicate message_id - this is expected and handled gracefully
        await db.rollback()
        
        # Track duplicate metric
        webhook_requests_total.labels(result='duplicate').inc()
        
        # Log duplicate detection
        logger.info(
            f"Duplicate message received: {payload.message_id}",
            extra={
                "extra_data": {
                    "message_id": payload.message_id,
                    "from": payload.from_msisdn,
                    "to": payload.to_msisdn,
                    "dup": True,
                }
            }
        )
        
        # Return 200 OK for idempotency (client doesn't need to retry)
        return JSONResponse(
            status_code=200,
            content={"status": "ok"}
        )
    
    except Exception as e:
        # Unexpected error - log and rollback
        await db.rollback()
        logger.error(
            f"Error processing webhook: {str(e)}",
            extra={
                "extra_data": {
                    "message_id": payload.message_id,
                    "error": str(e),
                }
            },
            exc_info=True
        )
        raise


# ============================================================================
# GET /messages Endpoint
# ============================================================================

@app.get("/messages", response_model=dict, status_code=200)
async def get_messages(
    limit: int = Query(default=50, ge=1, le=100, description="Number of messages to return (1-100)"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    from_msisdn: Optional[str] = Query(default=None, alias="from", description="Filter by exact sender phone number"),
    since: Optional[str] = Query(default=None, description="Filter messages with ts >= since"),
    q: Optional[str] = Query(default=None, description="Search text content"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Retrieve messages with filtering and pagination.
    
    Query Parameters:
        - limit: Number of messages to return (1-100, default 50)
        - offset: Offset for pagination (default 0)
        - from: Exact match on sender phone number
        - since: Filter messages with ts >= since
        - q: Text search in message content
    
    Returns:
        dict: {
            "data": List of messages ordered by ts ASC, message_id ASC,
            "total": Total count of messages matching filters
        }
    """
    # Build base query
    query = select(Message)
    count_query = select(func.count(Message.message_id))
    
    # Apply filters
    filters = []
    
    if from_msisdn:
        filters.append(Message.from_msisdn == from_msisdn)
    
    if since:
        filters.append(Message.ts >= since)
    
    if q:
        # Text search in message content
        filters.append(Message.text.ilike(f"%{q}%"))
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply ordering: ts ASC, message_id ASC
    query = query.order_by(Message.ts.asc(), Message.message_id.asc())
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Convert to response models
    data = [MessageResponse.model_validate(msg) for msg in messages]
    
    return {
        "data": data,
        "total": total
    }


# ============================================================================
# GET /stats Endpoint
# ============================================================================

@app.get("/stats", response_model=StatsResponse, status_code=200)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get aggregate statistics about messages.
    
    Returns:
        dict: {
            "total_messages": Total count of messages,
            "senders_count": Count of unique senders,
            "messages_per_sender": Top 10 senders with message counts,
            "first_message_ts": Timestamp of first message,
            "last_message_ts": Timestamp of last message
        }
    """
    # Get total messages count
    total_result = await db.execute(select(func.count(Message.message_id)))
    total_messages = total_result.scalar() or 0
    
    # Get unique senders count
    senders_result = await db.execute(
        select(func.count(func.distinct(Message.from_msisdn)))
    )
    senders_count = senders_result.scalar() or 0
    
    # Get top 10 senders with message counts
    messages_per_sender_query = (
        select(
            Message.from_msisdn,
            func.count(Message.message_id).label('count')
        )
        .group_by(Message.from_msisdn)
        .order_by(func.count(Message.message_id).desc())
        .limit(10)
    )
    messages_per_sender_result = await db.execute(messages_per_sender_query)
    messages_per_sender = [
        {"from_msisdn": row[0], "count": row[1]}
        for row in messages_per_sender_result.all()
    ]
    
    # Get first message timestamp
    first_msg_result = await db.execute(
        select(Message.ts).order_by(Message.ts.asc()).limit(1)
    )
    first_message_ts = first_msg_result.scalar()
    
    # Get last message timestamp
    last_msg_result = await db.execute(
        select(Message.ts).order_by(Message.ts.desc()).limit(1)
    )
    last_message_ts = last_msg_result.scalar()
    
    return {
        "total_messages": total_messages,
        "senders_count": senders_count,
        "messages_per_sender": messages_per_sender,
        "first_message_ts": first_message_ts,
        "last_message_ts": last_message_ts,
    }


# ============================================================================
# GET /metrics Endpoint (Prometheus)
# ============================================================================

@app.get("/metrics", status_code=200)
async def metrics() -> Response:
    """
    Expose Prometheus metrics.
    
    Metrics:
        - http_requests_total: Total HTTP requests (labels: path, status)
        - webhook_requests_total: Total webhook requests (labels: result)
    
    Returns:
        Response: Prometheus metrics in text format
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health/live", status_code=200)
async def liveness_check() -> dict:
    """
    Liveness probe - checks if the application is running.
    
    Returns:
        dict: {"status": "alive"}
    """
    return {"status": "alive"}


@app.get("/health/ready", status_code=200)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Readiness probe - checks if the application can serve traffic.
    
    Verifies database connectivity.
    
    Returns:
        dict: {"status": "ready"} if DB is accessible
    
    Raises:
        HTTPException: 503 if database is unreachable
    """
    try:
        # Test database connection
        await db.execute(select(1))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable"
        )


@app.get("/health", status_code=200)
async def health_check() -> dict:
    """
    Simple health check endpoint (deprecated, use /health/live or /health/ready).
    
    Returns:
        dict: {"status": "healthy"}
    """
    return {"status": "healthy"}


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/", status_code=200)
async def root() -> dict:
    """
    Root endpoint with API information.
    
    Returns:
        dict: API metadata
    """
    return {
        "name": "Webhook API",
        "version": "1.0.0",
        "status": "running",
    }
