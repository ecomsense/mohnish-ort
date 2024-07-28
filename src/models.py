from pydantic import BaseModel, Field


class ModelSettings(BaseModel):
    base: str = Field(default="BANKNIFTY")
    initial_quantity: int = Field(default=15, ge=1)
    stop_loss: float = Field(default=60.0, gt=0)
    expiry_offset: int = Field(default=1, ge=0)
