import os
import asyncio
from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator  

from citi_mesh import __version__
from citi_mesh.logging import get_logger
from citi_mesh.engine import CitiEngine
from citi_mesh.dev.demo import load_output_config, load_tools

logger = get_logger(__name__)

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info("App starting...")
    CitiEngine.get_instance(
        output_model=load_output_config(),
        tool_manager=load_tools()
    )

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

app = FastAPI()

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
        "cache": "ok" if cache_status else "error"
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
    request: Request, From: str = Form(...), Body: str = Form(...) 
):
    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    form_ = await request.form()
    logger.info(f"Message recieved from: {From}: {Body}")
    if not validator.validate(
        str(request.url), 
        form_, 
        request.headers.get("X-Twilio-Signature", "")
    ):
        raise HTTPException(status_code=400, detail="Error in Twilio Signature")


    response = await CitiEngine.chat(
        phone=From,
        message=Body
    )

    response = MessagingResponse()
    msg = response.message(response.message)
    return Response(content=str(response), media_type="application/xml")

if __name__ == "__main__":
    app.run(debug=True)
