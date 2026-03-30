from .sqlalchemy_base import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey

class CurrentClock(Base):
    __tablename__ = "current_clocks"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    start_time = Column(DateTime)