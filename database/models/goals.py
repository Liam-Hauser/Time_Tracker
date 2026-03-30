from .sqlalchemy_base import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    tasks_id = Column(Integer, ForeignKey("tasks.id"))
    name = Column(String)
    target_hours = Column(Integer)
    by_date = Column(DateTime)