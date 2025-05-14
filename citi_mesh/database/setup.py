import logging.config
import logging
import pathlib
import json

from sqlalchemy import MetaData
from citi_mesh.database.session import get_session, ENGINE
from citi_mesh.database.base import BaseTable
from citi_mesh.database.models import Tenant

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)


def setup_db(reset_db: bool = True, is_dev:bool = False):

    if reset_db:
        # Create a MetaData instance
        metadata = MetaData()

        # Reflect the existing tables from the database
        metadata.reflect(bind=ENGINE)

        # Drop all tables
        metadata.drop_all(bind=ENGINE)

        logger.info("All tables have been dropped successfully.")

    # Create all tables defined in the Base
    BaseTable.metadata.create_all(ENGINE)

    with get_session() as session:
        demo_tenant_json = json.loads(
            pathlib.Path("/Users/ryan/projects/CitiMesh/demo_tenant.json").read_text()
        )
        demo_tenant = Tenant.model_validate(demo_tenant_json)
        session.add(demo_tenant.to_orm())
        # Add tables here
        session.commit()


if __name__ == "__main__":

    setup_db()
