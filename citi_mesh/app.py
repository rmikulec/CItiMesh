import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator  

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


app = FastAPI(lifespan=app_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "FastAPI SMS Webhook App"}


@app.post("/sms")
async def sms(
    request: Request, From: str = Form(...), Body: str = Form(...) 
):
    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    form_ = await request.form()
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
