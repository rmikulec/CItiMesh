from pydantic_settings import BaseSettings
from pydantic import Field
import os
import urllib


class CitimeshConfig(BaseSettings):
    # Model Configuration
    parsing_model: str = Field(default="gpt-4o-mini")
    chat_model: str = Field(default="gpt-4o-2024-08-06")
    temperature: float = Field(default=0.4)
    default_model_parameters: dict = Field(default_factory=dict)

    # Database configuration
    default_database_name: str = Field(default="dev")
    default_database_connection_url: str = Field(default="")
    server: str = Field(default="citimesh-{env}.database.windows.net")
    database: str = Field(default="Resources")
    db_username: str = Field(default="azureadmin")
    db_password: str = Field(default=os.getenv("SQL_ADMIN_PASSWORD"))
    db_driver: str = Field(default="ODBC Driver 18 for SQL Server")

    # Service configuration
    conversation_expiration: int = Field(default=30)

    def __init__(self, **values):
        super().__init__(**values)
        # Set the database connection URL after the initial values have been set
        if not self.default_database_connection_url:
            pyoodbc_str = (
                "Driver={" + self.db_driver + "};"
                f"Server=tcp:{self.server.format(env='dev')},1433;"
                f"Database={self.database};"
                f"Uid={self.db_username};"
                "Pwd={" + self.db_password + "};"
                "Authentication=SqlPassword;"
                "Encrypt=yes;"
                "TrustServerCertificate=yes;"
                "Connection Timeout=30;"
            )
            self.default_database_connection_url = f"mssql+pyodbc:///?odbc_connect={pyoodbc_str}"


Config = CitimeshConfig()
