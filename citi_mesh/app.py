import asyncio
import io
import os
import pathlib
from contextlib import asynccontextmanager
from tempfile import TemporaryDirectory

import pandas as pd
from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request,
                     UploadFile, status)
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from twilio.request_validator import RequestValidator

from citi_mesh import __version__
from citi_mesh.database import _models
from citi_mesh.database.route_factory import RouteFactory
from citi_mesh.database.session import get_session_dependency, get_session
from citi_mesh.engine import CitiEngine
from citi_mesh.injestors import CSVInjestor, WebpageInjestor
from citi_mesh.logging import get_logger
from citi_mesh.utils import send_message_twilio, send_message_console

logger = get_logger(__name__)
TENANT_ID = '3bcaeb22-d367-4dec-b473-eb1fe329ceb2'

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    Infra to handle the Lifecycle of the app
    """
    logger.info("App starting...")
    async with get_session() as session:
        await CitiEngine().init(tenant_id='3bcaeb22-d367-4dec-b473-eb1fe329ceb2', session=session)

    yield

    logger.info("App shutting down...")


# Create the application
app = FastAPI(lifespan=app_lifespan, version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Use the RouteFactory to add any needed CRUD operations
route_factory = RouteFactory(app)
route_factory.add_routes(_models.Tenant)
route_factory.add_routes(_models.Repository)
route_factory.add_routes(_models.ResourceType)
route_factory.add_routes(_models.Resource)
route_factory.add_routes(_models.AnalyticConfig)


# --------------------Status Checks----------------------------------------
# TODO: Update these to actually check services
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


# --------------------SMS Webhooks----------------------------------------
@app.post("/sms/twilio", tags=["Webhooks"])
async def sms(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Webhook to recieve and send sms messages from a Twilio Service
    Note: 'TWILIO_AUTH_TOKEN' must be supplied to work
    """
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
        message=Body,
    )

    background_tasks.add_task(
        send_message_twilio, to=From, message_func=CitiEngine.chat, phone=From, message=Body
    )

@app.post("/dev/send_message", tags=["Developer"])
async def sms(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Developer tool to mock sending a message to the CitiEngine
    """
    engine = CitiEngine()

    background_tasks.add_task(
        send_message_console,
        to=From,
        message_func=engine.get_processing_message,
        phone=From,
        message=Body,
    )

    background_tasks.add_task(
        send_message_console, to=From, message_func=engine.chat, phone=From, message=Body
    )


# --------------------Submit Sources----------------------------------------
# TODO: Add more injestors, like PDF or word doc or excel


@app.post("/repository/{repository_id}/web", tags=["Repository"])
async def post_webpage_repository(
    repository_id: str, url: str, session=Depends(get_session_dependency)
):
    """
    Endpoint to add resources to a repository via a 'WebPage' source
    """
    repo = await _models.Repository.from_id(session=session, id_=repository_id)
    repo = WebpageInjestor(repo=repo, url=url)

    await repo.pull_resources(session)

    return status.HTTP_200_OK


@app.post("/repository/{repository_id}/csv", tags=["Repository"])
async def post_csv_repository(
    repository_id: str,
    csv_file: UploadFile = File(..., description="CSV file containing resources."),
    session=Depends(get_session_dependency),
):
    """
    Endpoint to add resources to a repository via a 'CSV' source
    """
    repo = await _models.Repository.from_id(session=session, id_=repository_id)
    # 2. Read & parse the CSV
    contents = await csv_file.read()
    text = contents.decode("utf-8")
    df = pd.read_csv(io.StringIO(text))
    # Use StringIO so csv.DictReader can treat it like a file
    with TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir) / "temp.csv"
        df.to_csv(temp_path)

        repo = CSVInjestor(repo_id=repository_id)

        await repo.pull_resources(session=session)


if __name__ == "__main__":
    app.run(debug=True)
