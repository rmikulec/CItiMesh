class InstanceNotFound(Exception):
    """
    Exception to be raised when an instance is not found in the database
    """

    def __init__(self, id_: str, model: str):
        self.message = f"{model} instance not found with id {id_}"
        super().__init__(self.message)
