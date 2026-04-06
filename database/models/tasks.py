from .sqlalchemy_base import Base
from sqlalchemy import Column, String, Integer, Boolean

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    category = Column(String)
    color = Column(String)
    archived = Column(Boolean, default=False)