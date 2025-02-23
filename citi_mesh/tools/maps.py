import googlemaps
import openai
import json
import os
import datetime

from citi_mesh.tools.base import BaseCitimeshTool

SYSTEM_MESSAGE = """You are an expert at interpreting results from the Google Maps API. 
You are designated with the task of recieving raw JSON output from google maps directions API, 
and must effectively communicate to the user, in text, of how to navigate to their destination. 
Keep in mind, that your result will eventually be sent to the user via SMS text message."""


class GoogleMapsDirectionsTool(BaseCitimeshTool):

    def __init__(self, *args, **kwargs):
        super().__init__(
            tool_name="get_directions",
            tool_desc="Get the directions between to places in NYC",
            args={
                "origin": {
                    "type": "string",
                    "description": "The place of origin, where the user is starting from.",
                },
                "destination": {"type": "string", "description": "Where the user wants to go"},
            },
            *args,
            **kwargs
        )

        self.gmaps = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API"])
        self.openai = openai.OpenAI()

    def _lookup_place(self, place_name):
        res = self.gmaps.find_place(place_name, input_type="textquery")
        return res["candidates"][0]["place_id"]

    def _clean_via_openai(self, directions_result: dict):
        response = self.openai.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": json.dumps(directions_result)},
            ],
            model="o1",
        )

        return response.choices[0].message.content

    def call(self, origin: str, destination: str) -> str:
        # Use Google Maps to convert the text lookup to place IDs
        origin_place_id = self._lookup_place(origin)
        destination_place_id = self._lookup_place(destination)

        # Query Google Maps Direction API
        directions_result = self.gmaps.directions(
            f"place_id:{origin_place_id}",
            f"place_id:{destination_place_id}",
            mode="transit",
            departure_time=datetime.datetime.now(),
        )

        # Cleanup the directions result with OpenAI
        # directions_result = self._clean_via_openai(directions_result)

        return json.dumps(directions_result)
