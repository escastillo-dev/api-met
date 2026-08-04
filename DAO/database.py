import os
from dotenv import load_dotenv
from sqlmodel import create_engine, Session

load_dotenv(override=True)

_host = os.getenv("DB_HOST")
_user = os.getenv("DB_USER")
_pass = os.getenv("DB_PASS")
_name = os.getenv("DB_NAME")
_port = os.getenv("DB_PORT", "3306")

DATABASE_URL = f"mysql+pymysql://{_user}:{_pass}@{_host}:{_port}/{_name}"

engine = create_engine(DATABASE_URL)


class Conexion:
    session = None

    def getSession(self):
        self.session = Session(engine)
        return self.session

    def cerrarSession(self):
        self.session.close()
