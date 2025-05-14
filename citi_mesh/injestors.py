import asyncio
import json
import pathlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union

import numpy as np
import openai
import pandas as pd
import requests
from pydantic import Field, create_model
from sqlalchemy.ext.asyncio import AsyncSession

from citi_mesh.config import Config
from citi_mesh.database._models import Address, Repository, Resource, Source


def create_resource_list_model(resource_types: list[tuple[str, str]]):
    """
    Return a pydantic model class that has a single field:
    `resources: List[DynamicResource]`
    where `DynamicResource` is the subclass generated from resource_types.
    """
    enum_name = "ResourceTypeEnum"
    type_map = {rt[0].upper().replace(" ", "_"): rt[0] for rt in resource_types}
    ResourceTypeEnum = Enum(enum_name, type_map, type=str)

    # Define the fields you want (omitting id, tenant_id, etc.).
    OpenAIResource = create_model(
        "OpenAIResource",
        name=(str, ...),
        description=(str, ...),
        phone_number=(Optional[str], None),
        website=(Optional[str], None),
        address=(Optional[Address], None),
        resource_types=(list[ResourceTypeEnum], Field(default_factory=list)),
    )

    ResourceList = create_model("ResourceList", resources=(list[OpenAIResource], ...))

    return ResourceList


SYSTEM_MESSAGE = """
You are an expert at normalizing government and non-profit data.
You will be provided a string of data, that will be in many different forms.
Your task is to, to the best of your ability, parse data out of that string in
a more structered format.

Please do not include any data that is not in the original string
Please do include all of the data that is in the string.
"""


class Injestor(ABC):
    """
    Injestors take in a form of data, a respository, and creates new resources based on that

    Injestor to be extending when creating a new type of 'repository'
    The base Injestor handles sending in the data to openai and then syncing it
    to the SQL Database

    To extend, the following must be implemented:
      - __init__(): The constructor can be used to introduce any new
        attributes that may be used when parsing the data. The class
        must send over a tenant_name and name to the BaseRepository when
        initializing
      - _parse_source(): This function must use any class attributes to
        create a list of strings that will later be sent to openai to pull out
        a more structured response. This function *must* return list[str]
    """

    __source_type__ = "base"

    def __init__(
        self,
        repo: Repository,
    ):
        self.repo = repo
        self.client = openai.AsyncClient()
        self.details = None

    @abstractmethod
    def _parse_source(self) -> list[str]:
        # Extend this method to provide 'source' material for
        # openai to parse resources from
        pass

    async def _sync_to_db(self, openai_resources: list[Resource], session: AsyncSession):
        """
        Private method to sync resources to the SQL Database
        """
        source = Source(
            repository_id=self.repo.id, source_type=self.__source_type__, details=self.details
        )
        await session.merge(source.to_orm())

        # Loop through the openai generated resources and
        # using the Tenant, create the proper resources to
        # add to the Repository
        for resource in openai_resources:
            new_resource = self.repo.create_resource_from_openai_resource(openai_resource=resource)
            await session.merge(new_resource.to_orm())

        await session.commit()
        await session.flush()

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
                response_format=create_resource_list_model(
                    resource_types=[(t.name, t.display_name) for t in self.repo.resource_types]
                ),
            )

            resources = completion.choices[0].message.parsed.resources

            return resources
        else:
            return []

    async def pull_resources(
        self, session: AsyncSession, debug: bool = False, chunk_size: int = 20
    ) -> Optional[list[Resource]]:
        """
        Pulls resources out of the original source and syncs them to the database

        Attributes:
          - debug (bool): If True, will skip syncing database and return the list
            of Resources instead. Defaults to False.
          - chunk_size: The size of each sublist that is sent over to openai. The bigger
            the chunk size, the faster it will run, but may result in lower accuracy.
            Defaults to 20.
        """
        source_data = self._parse_source()

        chunked_data = [
            source_data[i : i + chunk_size] for i in range(0, len(source_data), chunk_size)
        ]

        openai_results = await asyncio.gather(
            *[self._openai_parse(source_strings=source_strings) for source_strings in chunked_data]
        )

        resources = sum(openai_results, [])

        if not debug:
            await self._sync_to_db(resources, session=session)
        else:
            return resources


class WebpageInjestor(Injestor):
    """
    Repository class used to update the Resources DB with information
    from a given webpage

    Attributes:
      - repo( Repository): the repository SQLModel to add the new resources to
      - url(str): The URL of the webpage to sync with
    """

    __source_type__ = "webpage"

    def __init__(
        self,
        repo: Repository,
        url: str,
    ):
        self.url = url
        super().__init__(repo=repo)
        self.details = url

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


class CSVInjestor(Injestor):
    """
    Repository class used to update the Resources DB with information
    from a given CSV File

    Attributes:
      - repo( Repository): the repository SQLModel to add the new resources to
      - csv_path(str): Path to the csv to sync with
    """

    __source_type__ = "csv_file"

    def __init__(
        self,
        repo: Repository,
        csv_path: Union[str, pathlib.Path],
    ):
        self.csv_path = pathlib.Path(csv_path)
        super().__init__(repo=repo)
        self.details = self.csv_path.stem

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
