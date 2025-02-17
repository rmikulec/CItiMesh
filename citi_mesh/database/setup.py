import logging.config
import logging

from sqlalchemy import MetaData

from citi_mesh.config import Config
from citi_mesh.database.db_pool import DatabasePool
from citi_mesh.database.base import BaseTable
from citi_mesh.database import resource

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)


def setup_db(reset_db: bool = True):

    if not DatabasePool._instance:

        DatabasePool.get_instance(Config.default_database_connection_url)

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
        demo_tenant = resource.Tenant(
            name="demo", registered_number="+1 (908) 488-5426", url_extension="demo"
        )
        session.add(demo_tenant.to_orm())
        # Add tables here
        session.commit()


if __name__ == "__main__":

    setup_db()
