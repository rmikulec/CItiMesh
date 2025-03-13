import click
import json
import asyncio
from dotenv import load_dotenv

from citi_mesh.engine import CitiEngine
from citi_mesh.engine.logistic_models import Analytic, OpenAIOutput
from citi_mesh.tools import CitiToolManager


def load_output_config() -> OpenAIOutput:
    issue_type = Analytic(
        name="IssueType",
        description="The type of issue the citizen is reporting or asking about",
        value_type=str,
        possible_values=["Traffic", "Health", "Housing", "Food"],
    )

    severity = Analytic(
        name="Severity",
        description="The severity of the request or question the citizen asked",
        value_type=int,
    )

    OutputModel = OpenAIOutput.from_analytics(analytics=[issue_type, severity])

    return OutputModel


def load_tools():
    return CitiToolManager(tools=["google_maps"])


@click.command()
def chat():
    """A simple chat interface that processes user input."""
    click.echo("Welcome to the simple chat! Type 'exit' or 'quit' to leave.")

    engine = CitiEngine(output_model=load_output_config(), tools=load_tools())

    while True:
        # Prompt the user for a message.
        user_message = click.prompt("You", type=str)

        # Check for exit condition.
        if user_message.lower() in ["exit", "quit"]:
            click.echo("Exiting chat. Goodbye!")
            break

        # Process the message.
        bot_response = asyncio.run(engine.chat(user_message))

        # Send the processed message back.
        click.echo(f"CitiMesh: {bot_response.message}")
        click.echo(
            f"Analytics: {bot_response.model_dump_json(
            exclude=["message"],
            indent=2
        )}"
        )


if __name__ == "__main__":
    load_dotenv()

    chat()
