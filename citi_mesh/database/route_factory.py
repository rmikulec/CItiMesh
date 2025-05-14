from fastapi import Depends, FastAPI, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from citi_mesh.database._base import SQLModel
from citi_mesh.database._exceptions import InstanceNotFound
from citi_mesh.database.session import get_session_dependency


class RouteFactory:
    """
    Factory to create CRUD operation endpoints given a SQLModel

    Args:
        app(FastAPI): The FastAPI applicaiton to add the new endpoints to

    Methods:
        add_routes(model: SQlMode): Adds CRUD endpoints to the app


    Usage:
        # Define a factory
        factory = RouteFactory(my_app)
        # Add any models
        factory.add_routes(MyModelA)
        factory.add_routes(MyModelB)
    """

    def __init__(self, app: FastAPI):
        self.app = app

    def _create_get_endpoint(self, model):
        """
        Private factory method to create a 'GET' endpoint function given a SQLModel
        """

        async def _get(id: str, session: AsyncSession = Depends(get_session_dependency)):
            try:
                entity = await model.from_id(session=session, id_=id)
                return entity
            except InstanceNotFound as e:
                return Response(content=str(e), status_code=status.HTTP_404_NOT_FOUND)

        return _get

    def _create_add_endpoint(self, Model):
        """
        Private factory method to create a 'POST' endpoint function given a SQLModel
        """

        async def _add(data: Model, session: AsyncSession = Depends(get_session_dependency)):
            try:
                await data.upsert(session)
            except Exception as e:
                return Response(content=str(e), status_code=status.HTTP_404_NOT_FOUND)

        return _add

    def add_routes(self, Model: type[SQLModel]):
        """
        Add all CRUD routes to application given a SQLModel

        args:
            Model(SQLModel): A SQLModel class that will be exposed in the FastAPI application
        """
        # GET Endpoint
        self.app.get(
            f"/{Model.__name__.lower()}/{{id}}",
            name=f"{Model.__name__}.View",
            tags=["CRUD", Model.__name__],
        )(self._create_get_endpoint(Model))

        # POST Endpoint
        self.app.post(
            f"/{Model.__name__.lower()}/",
            name=f"{Model.__name__}.Create",
            tags=["CRUD", Model.__name__],
        )(self._create_add_endpoint(Model))
