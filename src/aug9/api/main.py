import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aug9.api.rate_limit import (
    RateLimitExceeded,
    product_event_rate_limiter,
    rate_limiter,
    visitor_session_global_rate_limiter,
)
from aug9.api.visitor_identity import (
    VISITOR_TOKEN_LIFETIME_SECONDS,
    VisitorTokenError,
    issue_visitor_token,
    resolve_visitor_identity,
)
from aug9.core.agent import run_aug9
from aug9.core.models import Place
from aug9.core.skill import SkillAction
from aug9.core.database import (
    database_is_ready,
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


DEFAULT_ALLOWED_ORIGINS = [
    "https://aug9.sg",
    "https://www.aug9.sg",
    "https://aug-nudge-now.base44.app",
]


def configured_allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or DEFAULT_ALLOWED_ORIGINS


app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_allowed_origins(),
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    task_id: str | None = Field(default=None, min_length=1, max_length=80)
    visitor_token: str | None = Field(default=None, min_length=1, max_length=512)
    latitude: float | None = Field(default=None, ge=1.1, le=1.5)
    longitude: float | None = Field(default=None, ge=103.6, le=104.1)
    location_label: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def coordinates_are_complete(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ChatResponse(BaseModel):
    response: str
    actions: list[SkillAction] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ProductEventResponse(BaseModel):
    accepted: bool = True


class ProductEventRequest(ProductEvent):
    visitor_token: str | None = Field(default=None, min_length=1, max_length=512)


class VisitorSessionResponse(BaseModel):
    visitor_token: str
    expires_in_seconds: int


@app.get("/")
def health_check():
    return {
        "status": "Aug9 API running"
    }


@app.get("/health/ready")
def readiness_check():
    if not database_is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "dependency": "database",
            },
        )
    return {"status": "ready"}


def try_log_usage(**kwargs) -> bool:
    """Keep analytics failures from changing the user-facing API outcome."""
    try:
        log_usage_event(**kwargs)
    except Exception:
        return False
    return True


def rate_limit_error(error: RateLimitExceeded, message: str) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "error": "rate_limit_exceeded",
            "message": message,
            "retry_after_seconds": error.retry_after_seconds,
        },
        headers={"Retry-After": str(error.retry_after_seconds)},
    )


@app.post("/visitor/session", response_model=VisitorSessionResponse)
def create_visitor_session():
    try:
        visitor_session_global_rate_limiter.check("visitor-session-global")
        return VisitorSessionResponse(
            visitor_token=issue_visitor_token(),
            expires_in_seconds=VISITOR_TOKEN_LIFETIME_SECONDS,
        )
    except RateLimitExceeded as error:
        raise rate_limit_error(
            error,
            "Too many visitor sessions were requested. Please try again shortly.",
        ) from error


@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
):
    started_at = time.perf_counter()
    effective_user_id = request.user_id

    try:
        visitor = resolve_visitor_identity(
            request.visitor_token,
            request.user_id,
        )
        effective_user_id = visitor.user_id
        rate_limiter.check(
            visitor.rate_limit_key
        )

        result = run_aug9(
            request.message,
            user_id=effective_user_id,
            session_id=request.session_id,
            structured=True,
            supplied_place=(
                Place(
                    name=request.location_label or "Current location",
                    place_type="browser_location",
                    latitude=request.latitude,
                    longitude=request.longitude,
                )
                if request.latitude is not None and request.longitude is not None
                else None
            ),
        )
        task_id = request.task_id or str(uuid4())
        result.metadata["task_id"] = task_id
        if visitor.token:
            result.metadata["visitor_token"] = visitor.token
            result.metadata["visitor_identity_verified"] = visitor.verified
        capabilities = result.metadata.get("requested_capabilities", [])
        capability_outcomes = result.metadata.get("capability_outcomes", {})
        result_status = (
            TaskStatus.FAILED
            if "unmatched" in capability_outcomes.values()
            else TaskStatus.ANSWER_GENERATED
        )

        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        background_tasks.add_task(
            try_log_usage,
            user_id=effective_user_id,
            session_id=request.session_id,
            message_length=len(
                request.message
            ),
            status="success",
            latency_ms=latency_ms,
        )
        background_tasks.add_task(
            try_log_product_event,
            ProductEvent(
                task_id=task_id,
                user_id=effective_user_id,
                session_id=request.session_id,
                event_type=ProductEventType.RESULT_GENERATED,
                capabilities=capabilities,
                task_status=result_status,
            )
        )

        return ChatResponse(
            response=result.response,
            actions=result.actions,
            metadata=result.metadata,
        )

    except VisitorTokenError as error:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_visitor_token",
                "message": str(error),
            },
        ) from error

    except RateLimitExceeded as error:
        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        try_log_usage(
            user_id=effective_user_id,
            session_id=request.session_id,
            message_length=len(
                request.message
            ),
            status="rate_limited",
            latency_ms=latency_ms,
            error_type="rate_limit_exceeded",
        )

        raise rate_limit_error(
            error,
            (
                "You've reached the Aug9 public beta usage limit. "
                "Please try again shortly."
            ),
        ) from error

    except Exception as error:
        latency_ms = int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )

        try_log_usage(
            user_id=effective_user_id,
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

        raise HTTPException(
            status_code=503,
            detail={
                "error": "temporarily_unavailable",
                "message": (
                    "Aug9 could not complete this request right now. "
                    "Please try again shortly."
                ),
            },
        ) from error


@app.post("/events", response_model=ProductEventResponse)
def product_event(event: ProductEventRequest):
    try:
        visitor = resolve_visitor_identity(
            event.visitor_token,
            event.user_id,
        )
        product_event_rate_limiter.check(visitor.rate_limit_key)
        event_data = event.model_dump(exclude={"visitor_token"})
        event_data["user_id"] = visitor.user_id
        log_product_event(ProductEvent(**event_data))
        return ProductEventResponse()
    except VisitorTokenError as error:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_visitor_token",
                "message": str(error),
            },
        ) from error
    except RateLimitExceeded as error:
        raise rate_limit_error(
            error,
            "Too many analytics events were submitted. Please try again shortly.",
        ) from error
