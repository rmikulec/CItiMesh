from fastapi import FastAPI, Form

app = FastAPI()


@app.get("/")
async def read_root():
    return {"message": "FastAPI SMS Webhook App"}


@app.post("/sms")
async def sms_webhook(
    From: str = Form(...), To: str = Form(...), Body: str = Form(...), MessageSid: str = Form(...)
):
    # Log the incoming message details
    print("Received SMS:")
    print("From:", From)
    print("To:", To)
    print("Body:", Body)
    print("MessageSid:", MessageSid)

    # For now, just return a confirmation in JSON
    return {"status": "received"}
