import logging.config
import logging
import pathlib
import json

from sqlalchemy import MetaData

from citi_mesh.config import Config
from citi_mesh.database.db_pool import DatabasePool
from citi_mesh.database.base import BaseTable
from citi_mesh.database.models import Tenant

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)


def setup_db(reset_db: bool = True, is_dev:bool = False):

    if not DatabasePool._instance:

        if is_dev :
            DatabasePool.get_instance(connection_url="sqlite:///dev.db")
        else:
            DatabasePool.get_instance(connection_url=Config.default_database_connection_url)

    if reset_db:
        # Create a MetaData instance
        metadata = MetaData()

        # Reflect the existing tables from the database
        metadata.reflect(bind=DatabasePool._engine)

        # Drop all tables
        metadata.drop_all(bind=DatabasePool._engine)

        logger.info("All tables have been dropped successfully.")

    # Create all tables defined in the Base
    BaseTable.metadata.create_all(DatabasePool._engine)

    with DatabasePool.get_session() as session:
        demo_tenant_json = json.loads(
            pathlib.Path("/Users/ryan/projects/CitiMesh/demo_tenant.json").read_text()
        )
        demo_tenant = Tenant.model_validate(demo_tenant_json)
        session.add(demo_tenant.to_orm())
        # Add tables here
        session.commit()


if __name__ == "__main__":

    setup_db()
