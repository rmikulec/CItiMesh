import os
import asyncio
from io import BytesIO
from fastapi import FastAPI, Request, Form, HTTPException, status, BackgroundTasks, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator

from citi_mesh import __version__
from citi_mesh.logging import get_logger
from citi_mesh.engine import CitiEngine
from citi_mesh.data.provider import CSVProvider, WebpageProvider
from citi_mesh.utils import send_message_twilio
from citi_mesh.dev.demo import load_output_config, load_tools
from citi_mesh.database.models import Provider

logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info("App starting...")
    tools = await load_tools()
    CitiEngine.get_instance(output_model=load_output_config(), tool_manager=tools)

    yield

    logger.info("App shutting down...")


app = FastAPI(lifespan=app_lifespan, version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Example async functions that check dependencies.
# Replace the contents of these functions with your actual health-check logic.


async def check_database():
    try:
        # For example, perform a simple query or connection test.
        # await your_database.execute("SELECT 1")
        await asyncio.sleep(0.1)  # Simulate IO-bound operation
        return True
    except Exception as e:
        return False


async def check_cache():
    try:
        # For example, ping your cache (Redis, Memcached, etc.)
        # await redis_client.ping()
        await asyncio.sleep(0.1)  # Simulate IO-bound operation
        return True
    except Exception as e:
        return False


@app.get("/health", tags=["Health"])
async def health_check():
    # Run dependency checks concurrently.
    db_status, cache_status = await asyncio.gather(check_database(), check_cache())

    # Build a status response for each dependency.
    components = {
        "database": "ok" if db_status else "error",
        "cache": "ok" if cache_status else "error",
    }

    # Determine the overall health.
    overall_healthy = all([db_status, cache_status])
    if overall_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "components": components},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "components": components},
        )


@app.post("/sms")
async def sms(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
):
    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    form_ = await request.form()
    logger.info(f"Message recieved from: {From}: {Body}")
    if not validator.validate(
        str(request.url), form_, request.headers.get("X-Twilio-Signature", "")
    ):
        raise HTTPException(status_code=400, detail="Error in Twilio Signature")


    background_tasks.add_task(
        send_message_twilio, 
        to=From,
        message_func=CitiEngine.get_processing_message, 
        phone=From,
        message=Body
    )


    background_tasks.add_task(
        send_message_twilio,
        to=From,
        message_func=CitiEngine.chat,
        phone=From,
        message=Body
    )


@app.post("/provider/{tenant_id}")
def post_webpage_provider(provider: Provider, webpage: str):
    pass

if __name__ == "__main__":
    app.run(debug=True)


