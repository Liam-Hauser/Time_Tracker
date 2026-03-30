from sqlalchemy_base import Base
from sqlalchemy import Column, Integer, String, DateTime

class HistoricClock(Base):
    __tablename__ = "historic_clocks"

    id = Column(Integer, primary_key=True)
    taks_id = Column(Integer, foreign_key="tasks.id")
    total_sec = Column(Integer)
    start_time = Column(DateTime)
    end_time = Column(DateTime)