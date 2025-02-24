from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from citi_mesh.engine import CitiEngine
from citi_mesh.dev.demo import load_output_config, load_tools

app = FastAPI()

engine = CitiEngine.get_instance(
    output_model=load_output_config(),
    tool_manager=load_tools()
)

@app.get("/")
async def read_root():
    return {"message": "FastAPI SMS Webhook App"}


@app.post("/sms")
async def sms_reply(request: Request):
    # Retrieve form data from the incoming POST request
    form = await request.form()
    incoming_msg = form.get("Body", "")
    from_number = form.get("From", "")

    response = await engine.chat(
        phone=from_number,
        message=incoming_msg
    )

    # Create a TwiML response object to reply to the sender
    resp = MessagingResponse()
    resp.message(response.message)

    # Optional: Use the REST API to send an additional message
    # client.messages.create(
    #     body="This is an extra message sent via the Twilio API!",
    #     from_='+YourTwilioNumber',
    #     to=from_number
    # )

    # Return the TwiML as XML
    return Response(content=str(resp), media_type="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
