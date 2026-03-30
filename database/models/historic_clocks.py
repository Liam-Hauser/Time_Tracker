from .sqlalchemy_base import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey

class HistoricClock(Base):
    __tablename__ = "historic_clocks"

    id = Column(Integer, primary_key=True)
    tasks_id = Column(Integer, ForeignKey("tasks.id"))
    total_sec = Column(Integer)
    start_time = Column(DateTime)
    end_time = Column(DateTime)