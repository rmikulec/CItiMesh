from citi_mesh.logging import get_logger
from citi_mesh.database.session import get_session
from citi_mesh.database.models import Tenant
from citi_mesh.engine.analytic_models import Analytic, OpenAIOutput
from citi_mesh.tools import CitiToolManager
from citi_mesh.tools.provider import ProviderTool

logger = get_logger(__name__)


def load_output_config() -> OpenAIOutput:
    logger.info("Loading base output config...")
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


async def load_tools():
    async with get_session() as session:
        tenant = await Tenant.from_id(session, '3bcaeb22-d367-4dec-b473-eb1fe329ceb2')
        return CitiToolManager(
            tools=[
                ProviderTool(
                    provider=tenant.providers[0]
                )
            ]
        )
