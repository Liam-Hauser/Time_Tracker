from .sqlalchemy_base import Base
from sqlalchemy import Column, String, Integer


class Category(Base):
    __tablename__ = "categories"

    id         = Column(Integer, primary_key=True)
    name       = Column(String, unique=True)
    colour_tag = Column(String)   # key into TAG_PALETTES, e.g. "blue"
