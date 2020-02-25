
import os
import sys

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(CUR_DIR, "sqlalchemy-utils"))
sys.path.insert(0, os.path.join(CUR_DIR, "sqlalchemy/lib"))

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy import Column, Table, Text, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import database_exists, create_database


db_name = "debdb"
db_string = f"postgres+psycopg2://postgres@localhost/{db_name}"
Base = declarative_base(db_string)


class Packages(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True)
    pkgname = Column(Text)
    debname = Column(Text)
    filepath = Column(Text)


class Database(object):
    def __init__(self):
        if not database_exists(db_string):
            create_database(db_string)

        self.db = create_engine(db_string)
        self.Session = sessionmaker(self.db)

        Base.metadata.create_all()

    def newsession(self):
        self.session = self.Session()

    def closesession(self):
        self.session.close()

    def insert(self, ent):
        self.session.add(ent)
        self.session.commit()

    def erase(self):
        drop_database(db_string)

