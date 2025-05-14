from citi_mesh.database._base import SQLModel
from citi_mesh.database._exceptions import InstanceNotFound
from citi_mesh.database.session import get_session_dependency

from fastapi import Response, FastAPI, Depends
from starlette import status

from sqlalchemy.ext.asyncio import AsyncSession

class RouteFactor:

    def __init__(self, app: FastAPI):
        self.app = app

    
    def _create_get_endpoint(self, model):
        async def _get(id: str, session: AsyncSession = Depends(get_session_dependency)):
            try:
                entity = await model.from_id(session=session, id_=id)
                return entity
            except InstanceNotFound as e:
                return Response(
                    content=str(e),
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        return _get
    
    def _create_add_endpoint(self, Model):
        async def _add(*parent_ids, data: Model, session: AsyncSession = Depends(get_session_dependency)):
            try:
                await data.sync_to_db(session)
            except Exception as e:
                return Response(
                    content=str(e),
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        return _add


    def add_routes(self, Model: SQLModel):
        # GET Endpoint
        self.app.get(
            f"/{Model.__name__.lower()}/{{id}}", 
            name=f"{Model.__name__}.View",
            tags=["CRUD", Model.__name__]
        )(self._create_get_endpoint(Model))

        # POST Endpoint
        self.app.post(
            f"/{Model.__name__.lower()}/", 
            name=f"{Model.__name__}.Create",
            tags=["CRUD", Model.__name__]
        )(self._create_add_endpoint(Model))