import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.models.schemas import MessageResponse, WebhookMessage
from app.services.handler import get_settings, handle_webhook_message

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting Guest Message Handler v%s | model=%s", settings.app_version, settings.claude_model)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Nistula Guest Message Handler",
    description="Classifies and responds to villa guest messages via Claude AI.",
    version=get_settings().app_version,
    lifespan=lifespan,
)


@app.post(
    "/webhook/message",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Process an inbound guest message",
)
async def webhook_message(payload: WebhookMessage):
    try:
        return await handle_webhook_message(payload)
    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.error("Unhandled error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message. Please try again.",
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Global exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )
