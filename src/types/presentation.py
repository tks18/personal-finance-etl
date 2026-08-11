from pydantic import BaseModel, ConfigDict


class PresentationEngineConfig(BaseModel):
    """Configuration passed into the presentation engine modules."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True)
    # To be expanded as we refactor the presentation modules
