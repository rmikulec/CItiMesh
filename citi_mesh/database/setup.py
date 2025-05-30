import json
import logging
import pathlib

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from citi_mesh.database._base import SQLTable
from citi_mesh.database._models import Tenant

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)


def setup_db(reset_db: bool = True, is_dev: bool = False):
    """
    Helper function to create and setup the database
    """
    # Create a syncronous engine
    ENGINE = create_engine(url="sqlite:///dev.db")
    if reset_db:
        # Create a MetaData instance
        metadata = MetaData()

        # Reflect the existing tables from the database
        metadata.reflect(bind=ENGINE)

        # Drop all tables
        metadata.drop_all(bind=ENGINE)

        logger.info("All tables have been dropped successfully.")

    # Create all tables defined in the Base
    SQLTable.metadata.create_all(ENGINE)

    try:
        session = Session(bind=ENGINE)
        demo_tenant_json = json.loads(
            pathlib.Path("/Users/ryan/projects/CitiMesh/demo_tenant.json").read_text()
        )
        demo_tenant = Tenant.model_validate(demo_tenant_json)
        session.add(demo_tenant.to_orm())
        # Add tables here
        session.commit()
    finally:
        session.close()


# Setup so it can be run as a script as well
if __name__ == "__main__":
    setup_db()
