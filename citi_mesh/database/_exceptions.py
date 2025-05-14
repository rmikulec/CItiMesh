class InstanceNotFound(Exception):

    def __init__(self, id_: str, model: str):
        self.message = (
            f"{model} instance not found with id {id_}"
        )
        super().__init__(self.message)