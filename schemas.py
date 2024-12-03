from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class NetworkConnectionCreate(BaseModel):
    hostname: str = Field(..., description="Hostname or IP address of the network device")
    username: str
    password: str
    device_type: str

class NetworkConnectionResponse(BaseModel):
    id: int
    hostname: str
    device_type: str
    is_connected: bool
    last_connected: datetime
    last_check: datetime

    model_config = ConfigDict(from_attributes=True)