from pydantic import BaseModel, Field, create_model

from citi_mesh.database._models import AnalyticConfig

class OpenAIOutput(BaseModel):
    message: str = Field(..., description="Response to the user's query")

    @classmethod
    def from_analytics(cls, analytics: list[AnalyticConfig]):
        field_definitions = {analytic.name: analytic.field_definition for analytic in analytics}

        return create_model("ExtendedOpenAIOutput", __base__=cls, **field_definitions)