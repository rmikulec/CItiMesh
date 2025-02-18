import openai
import requests
import asyncio
import pathlib
import json
import pandas as pd
import numpy as np
from abc import abstractmethod, ABC
from pydantic import BaseModel, create_model
from functools import cached_property
from typing import Union, Optional, Literal
from sqlalchemy.orm import Session
from enum import Enum

from citi_mesh.database.crud import get_tenant_from_name
from citi_mesh.database.resource import Resource, Provider, Tenant
from citi_mesh.database.db_pool import DatabasePool
from citi_mesh.config import Config



def create_resource_list_model(tenant: Tenant):
    """
    Return a pydantic model class that has a single field:
    `resources: List[DynamicResource]`
    where `DynamicResource` is the subclass generated from resource_types.
    """
    DynamicResource = tenant.create_resource_openai_class()

    ResourceList = create_model(
        "ResourceList",
        resources=(list[DynamicResource], ...)
    )

    return ResourceList

    


SYSTEM_MESSAGE = """
You are an expert at normalizing government and non-profit data.
You will be provided a string of data, that will be in many different forms.
Your task is to, to the best of your ability, parse data out of that string in
a more structered format.

Please do not include any data that is not in the original string
Please do include all of the data that is in the string.
"""


class BaseProvider(ABC):
    """
    Base Provider to be extending when creating a new type of 'source'
    The BaseProvider handles sending in the data to openai and then syncing it
    to the SQL Database

    To extend, the following must be implemented:
      - __init__(): The constructor can be used to introduce any new
        attributes that may be used when parsing the data. The class
        must send over a tenant_name and name to the BaseProvider when
        initializing
      - _parse_source(): This function must use any class attributes to
        create a list of strings that will later be sent to openai to pull out
        a more structured response. This function *must* return list[str]
    """

    __source_type__ = "base"

    def __init__(self, tenant_name: str, name: str, session: Session):
        self.tenant_name = tenant_name
        self.name = name
        self.session = session
        self.client = openai.AsyncClient()
        self.db_pool = DatabasePool.get_instance()


    @cached_property
    def tenant(self) -> Tenant:
        return get_tenant_from_name(session=self.session, tenant_name=self.tenant_name)

    @abstractmethod
    def _parse_source(self) -> list[str]:
        # Extend this method to provide 'source' material for
        # openai to parse resources from
        pass

    def _sync_to_db(self, openai_resources: list[Resource]):
        """
        Private method to sync resources to the SQL Database
        """

        # Create the new provider with empty resources
        provider = Provider(
            tenant_id=self.tenant.id,
            name=self.name,
            provider_type=self.__source_type__,
            resources=[],
        )

        # Loop through the openai generated resources and
        # using the Tenant, create the proper resources to
        # add to the Provider
        for resource in openai_resources:
            new_resource = self.tenant.create_resource_from_openai_resource(
                openai_resource=resource,
                provider_id=provider.id
            )
            provider.resources.append(new_resource)

        self.session.merge(provider.to_orm())
        self.session.commit()
        self.session.flush()

    async def _openai_parse(self, source_strings: list[str]) -> list[Resource]:
        """
        Private method to extract the strucuted resource from a list of strings
        that may contain those resources
        """
        # Check string for bad content
        content_check = await self.client.moderations.create(
            input="\n".join(source_strings),
        )

        if not content_check.results[0].flagged:
            completion = await self.client.beta.chat.completions.parse(
                model=Config.parsing_model,
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": "\n".join(source_strings)},
                ],
                response_format=create_resource_list_model(self.tenant),
            )

            resources = completion.choices[0].message.parsed.resources

            return resources
        else:
            return []

    async def pull_resources(
        self, debug: bool = False, chunk_size: int = 20
    ) -> Optional[list[Resource]]:
        """
        Pulls resources out of the original source and syncs them to the database

        Attributes:
          - debug (bool): If True, will skip syncing database and return the list
            of Resources instead. Defaults to False.
          - chunk_size: The size of each sublist that is sent over to openai. The bigger
            the chunk size, the faster it will run, but may result in lower accuracy.
            Defaults to 25.
        """
        source_data = self._parse_source()

        chunked_data = [
            source_data[i : i + chunk_size] for i in range(0, len(source_data), chunk_size)
        ]

        openai_results = await asyncio.gather(
            *[self._openai_parse(source_strings=source_str) for source_str in chunked_data]
        )

        resources = sum(openai_results, [])

        if not debug:
            self._sync_to_db(resources)
        else:
            return resources


class WebpageProvider(BaseProvider):
    """
    Provider class used to update the Resources DB with information
    from a given webpage

    Attributes:
      - tenant_name; The name of the organization or city using the system
      - name: The name of this particular provider (i.e. NYC Open Data)
      - url: The url of the webpage where the information is located
    """

    __source_type__ = "webpage"

    def __init__(self, tenant_name: str, name: str, session: Session, url: str):
        self.url = url
        super().__init__(tenant_name=tenant_name, name=name, session=session)

    def _parse_source(self):
        """
        Private function that uses the requests library to pull the
        raw HTML from the webpage
        """

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/98.0.4758.102 Safari/537.36"
        }
        response = requests.get(url=self.url, headers=headers)

        return [response.text]


class CSVProvider(BaseProvider):
    """
    Provider class used to update the Resources DB with information
    from a given CSV File

    Attributes:
      - tenant_name; The name of the organization or city using the system
      - name: The name of this particular provider (i.e. NYC Open Data)
      - csv_path: The path to the csv containing the information
    """

    __source_type__ = "csv_file"

    def __init__(self, tenant_name: str, name: str, session: Session, csv_path: Union[str, pathlib.Path]):
        self.csv_path = pathlib.Path(csv_path)
        super().__init__(tenant_name=tenant_name, name=name, session=session)

    def _parse_source(self):
        """
        Private function that uses the csv to create a list of
        json strings for each row in the file
        """
        df = pd.read_csv(self.csv_path)
        # Replace all np.nan with Python None
        # This is so that the rows are JSON Serializable
        df = df.replace({np.nan: None})
        records_array = df.to_dict(orient="records")
        return [json.dumps(record, indent=2) for record in records_array]
