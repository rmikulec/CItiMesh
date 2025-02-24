from citi_mesh.logging import get_logger
from citi_mesh.database.db_pool import DatabasePool
from citi_mesh.database.crud import get_tenant_from_name
from citi_mesh.engine.logistic_models import Analytic, OpenAIOutput
from citi_mesh.tools import CitiToolManager


logger = get_logger(__name__)

DatabasePool.get_instance()


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


def load_tools():
    with DatabasePool.get_session() as session:
        tenant = get_tenant_from_name(session=session, tenant_name="demo")
        return CitiToolManager(tools=["google_maps", "resources"], tenant=tenant, session=session)
