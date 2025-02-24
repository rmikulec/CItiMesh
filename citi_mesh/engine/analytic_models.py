from pydantic import BaseModel, create_model, Field
from typing import Literal, Any, Type, Optional


class Analytic(BaseModel):
    name: str
    description: str
    value_type: Type[Any]
    possible_values: Optional[list[str]] = None

    @property
    def _values_enum(self):
        return Literal[tuple([v for v in self.possible_values])]

    @property
    def field_definition(self):
        if self.possible_values:
            return (self._values_enum, Field(..., description=self.description))

        else:
            return (self.value_type, Field(..., description=self.description))


class OpenAIOutput(BaseModel):
    message: str = Field(..., description="Response to the user's query")

    @classmethod
    def from_analytics(cls, analytics: list[Analytic]):
        field_definitions = {analytic.name: analytic.field_definition for analytic in analytics}

        return create_model("ExtendedOpenAIOutput", __base__=cls, **field_definitions)
