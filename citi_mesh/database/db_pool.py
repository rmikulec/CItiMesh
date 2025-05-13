from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
from contextlib import contextmanager
import threading
import logging

from citi_mesh.config import Config

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)


class UninitializedDatabasePoolError(Exception):
    """Exception raised when attempting to access an uninitialized database pool."""

    def __init__(self, message=None):
        super().__init__(
            message or "DatabasePool is not initialized. Call `get_instance()` first."
        )


class DatabasePool:
    """Singleton class to manage database connection pooling using SQLAlchemy."""

    _instance = None
    _lock = threading.Lock()
    _engine: Optional[Engine] = None
    _sessionmaker: Optional[sessionmaker] = None

    @classmethod
    def get_instance(
        cls,
        connection_url: str = Config.default_database_connection_url,
        pool_size: int = 5,
        pool_timeout: Optional[float] = None,
    ):
        """
        Get the singleton instance of DatabasePool. Initializes the pool if not already initialized.

        :param connection_url: Database connection URL (required for first initialization).
        :param pool_size: Number of connections in the pool (default: 5).
        :param pool_timeout: Timeout for acquiring a connection from the pool (default: None).
        :return: Instance of DatabasePool.
        """
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    if not connection_url:
                        raise ValueError(
                            "Connection URL must be provided for the first initialization."
                        )
                    print(connection_url)
                    cls._instance = cls()
                    cls._engine = create_engine(
                        url=connection_url,
                        pool_size=pool_size,
                        pool_timeout=pool_timeout,
                        future=True,  # Use SQLAlchemy 2.0-style API
                    )
                    cls._sessionmaker = sessionmaker(
                        bind=cls._engine, autoflush=False, autocommit=False, expire_on_commit=False
                    )
                    logger.debug(
                        "DatabasePool initialized with connection_url=%s, pool_size=%d, pool_timeout=%s",
                        connection_url[0:25],
                        pool_size,
                        pool_timeout,
                    )
        return cls._instance

    @staticmethod
    def _handle_session_closure(session: Session):
        """
        Handle the closure of a session and log any errors.

        :param session: The SQLAlchemy Session object to close.
        """
        try:
            session.close()
            logger.debug("Database session closed successfully.")
        except Exception as e:
            logger.error(
                "Error occurred while closing database session: %s", str(e), exc_info=True
            )

    @classmethod
    @contextmanager
    def get_session(cls) -> Generator[Session, None, None]:
        """
        Provide a database session from the sessionmaker.

        :yield: A SQLAlchemy Session object.
        """
        if not cls._sessionmaker:
            logger.error("DatabasePool is not initialized. Call `get_instance()` first.")
            raise UninitializedDatabasePoolError()
        session = cls._sessionmaker()
        try:
            yield session
        finally:
            cls._handle_session_closure(session)

    @classmethod
    def shutdown(cls):
        """
        Dispose of the database connection pool and reset the instance.
        """
        with cls._lock:
            if cls._engine:
                logger.debug("Shutting down DatabasePool.")
                cls._engine.dispose()
                cls._engine = None
                cls._sessionmaker = None
                cls._instance = None
                logger.debug("DatabasePool shut down successfully.")
