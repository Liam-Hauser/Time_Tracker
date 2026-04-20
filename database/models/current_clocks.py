from .sqlalchemy_base import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text

class CurrentClock(Base):
    __tablename__ = "current_clocks"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    start_time = Column(DateTime)
    note = Column(Text, nullable=True)