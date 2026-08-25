import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aug9.api.rate_limit import (
    RateLimitExceeded,
    rate_limiter,
)
from aug9.core.agent import run_aug9
from aug9.core.skill import SkillAction
from aug9.core.database import (
    initialise_database,
    log_usage_event,
)
from aug9.core.product_analytics import (
    ProductEvent,
    ProductEventType,
    TaskStatus,
    log_product_event,
    try_log_product_event,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialise_database()
    yield


app = FastAPI(
    title="Aug9 API",
    version="0.1.0",
    lifespan=lifespan,
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
    task_id: str | None = Field(default=None, max_length=80)


class ChatResponse(BaseModel):
    response: str
    actions: list[SkillAction] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ProductEventResponse(BaseModel):
    accepted: bool = True


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
):
    started_at = time.perf_counter()

    try:
        rate_limiter.check(
            request.user_id
        )

        result = run_aug9(
            request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            structured=True,
        )
        task_id = request.task_id or str(uuid4())
        result.metadata["task_id"] = task_id
        capabilities = result.metadata.get("requested_capabilities", [])

        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        log_usage_event(
            user_id=request.user_id,
            session_id=request.session_id,
            message_length=len(
                request.message
            ),
            status="success",
            latency_ms=latency_ms,
        )
        try_log_product_event(
            ProductEvent(
                task_id=task_id,
                user_id=request.user_id,
                session_id=request.session_id,
                event_type=ProductEventType.RESULT_GENERATED,
                capabilities=capabilities,
                task_status=TaskStatus.ANSWER_GENERATED,
            )
        )

        return ChatResponse(
            response=result.response,
            actions=result.actions,
            metadata=result.metadata,
        )

    except RateLimitExceeded as error:
        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        log_usage_event(
            user_id=request.user_id,
            session_id=request.session_id,
            message_length=len(
                request.message
            ),
            status="rate_limited",
            latency_ms=latency_ms,
            error_type="rate_limit_exceeded",
        )

        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    "You've reached the Aug9 "
                    "public beta usage limit. "
                    "Please try again shortly."
                ),
                "retry_after_seconds": (
                    error.retry_after_seconds
                ),
            },
            headers={
                "Retry-After": str(
                    error.retry_after_seconds
                )
            },
        )

    except Exception as error:
        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        log_usage_event(
            user_id=request.user_id,
            session_id=request.session_id,
            message_length=len(
                request.message
            ),
            status="error",
            latency_ms=latency_ms,
            error_type=type(
                error
            ).__name__,
        )

        raise


@app.post("/events", response_model=ProductEventResponse)
def product_event(event: ProductEvent):
    log_product_event(event)
    return ProductEventResponse()
