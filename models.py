from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base
from datetime import datetime

class NetworkConnection(Base):
    __tablename__ = "network_connections"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, index=True)  # Can be DNS name or IP address
    username = Column(String)
    device_type = Column(String)
    is_connected = Column(Boolean, default=False)
    last_connected = Column(DateTime, default=datetime.utcnow)
    last_check = Column(DateTime, default=datetime.utcnow)