import time

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from aug9.core.database import log_usage_event
from aug9.core.agent import run_aug9
from aug9.api.rate_limit import (
    RateLimitExceeded,
    rate_limiter,
)


app = FastAPI(
    title="Aug9 API",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str


class ChatResponse(BaseModel):
    response: str


@app.get("/")
def health_check():
    return {
        "status": "Aug9 API running"
    }


@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    response: Response,
):
    started_at = time.perf_counter()

    try:
        rate_limiter.check(
            request.user_id
        )

    except RateLimitExceeded as error:
        response.headers["Retry-After"] = str(
            error.retry_after_seconds
        )

        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    "You've reached the Aug9 public beta "
                    "usage limit. Please try again shortly."
                ),
                "retry_after_seconds": (
                    error.retry_after_seconds
                ),
            },
        )

    result = run_aug9(
        request.message,
        user_id=request.user_id,
        session_id=request.session_id,
    )

    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    log_usage_event(
        user_id=request.user_id,
        session_id=request.session_id,
        message_length=len(request.message),
        status="success",
        latency_ms=latency_ms,
    )

    return ChatResponse(
        response=result
    )
except RateLimitExceeded as error:
    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    log_usage_event(
        user_id=request.user_id,
        session_id=request.session_id,         
        message_length=len(request.message),
        status="rate_limited",
        latency_ms=latency_ms,
        error_type="rate_limit_exceeded",
    )

    response.headers["Retry-After"] = str(
        error.retry_after_seconds
    )

    raise HTTPException(
        status_code=429,
        detail={
            "error": "rate_limit_exceeded",
            "message": (
                "You've reached the Aug9 public beta "
                "usage limit. Please try again shortly."
            ),
            "retry_after_seconds": (
                error.retry_after_seconds
            ),
        },
    )
except Exception as error:
    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    log_usage_event(
        user_id=request.user_id,
        session_id=request.session_id,
        message_length=len(request.message),
        status="error",
        latency_ms=latency_ms,
        error_type=type(error).__name__,
    )

    raise
