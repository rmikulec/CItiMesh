import os
import io
import asyncio
import pathlib
import pandas as pd
from tempfile import TemporaryDirectory
from pydantic import BaseModel, ValidationError
from fastapi import FastAPI, Request, Form, HTTPException, status, BackgroundTasks, UploadFile, File, Depends
from starlette import status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
from twilio.request_validator import RequestValidator

from citi_mesh import __version__
from citi_mesh.logging import get_logger
from citi_mesh.engine import CitiEngine
from citi_mesh.data.provider import CSVProvider, WebpageProvider
from citi_mesh.utils import send_message_twilio
from citi_mesh.dev.demo import load_output_config, load_tools
from citi_mesh.database.models import Provider
from citi_mesh.database.session import get_session_dependency

logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info("App starting...")
    #tools = await load_tools()
    CitiEngine.get_instance(output_model=load_output_config(), tool_manager=[])

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


@app.post("/sms", tags=['webhooks'])
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



class ProviderSubmissionResponse(BaseModel):
    pass


@app.post("/provider/web/{tenant_name}", tags=['provider'])
async def post_webpage_provider(
    tenant_name: str, 
    webpage: str, 
    provider: Provider, 
    session= Depends(get_session_dependency)
):
    repo = WebpageProvider(
        tenant_name=tenant_name,
        name=provider.name,
        display_name=provider.display_name,
        tool_description=provider.tool_description,
        types_=[
            (t.name, t.display_name)
            for t in provider.resource_types
        ],
        url=webpage
    )

    await repo.pull_resources(session)

    return status.HTTP_200_OK


@app.post("/provider/csv/{tenant_name}", tags=['provider'])
async def post_csv_provider(
    tenant_name: str,
    provider: str = Form(..., description="Provider metadata"),
    csv_file: UploadFile = File(..., description="CSV file containing resources."),
    session = Depends(get_session_dependency)
):
    try:
        meta = Provider.model_validate_json(provider)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # 2. Read & parse the CSV
    contents = await csv_file.read()
    text = contents.decode("utf-8")
    df = pd.read_csv(io.StringIO(text))
    # Use StringIO so csv.DictReader can treat it like a file
    with TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir) / "temp.csv"
        df.to_csv(temp_path)

        repo = CSVProvider(
            tenant_name=tenant_name,
            csv_path=temp_path,
            name=meta.name,
            display_name=meta.display_name,
            tool_description=meta.tool_description,
            types_=[
                (t.name, t.display_name)
                for t in meta.resource_types
            ],
        )

        await repo.pull_resources(session=session)


if __name__ == "__main__":
    app.run(debug=True)


