from sqlmodel import create_engine, Session
#DATABASE_URL='mysql+pymysql://root:root@localhost:3306/scisp'
DATABASE_URL='mysql+pymysql://ecastillo:Cachopp2@mysql-met.mysql.database.azure.com:3306/scisp'
engine = create_engine(DATABASE_URL)

class Conexion:
    session=None
    def getSession(self):
        self.session = Session(engine)
        return self.session
    def cerrarSession(self):
        self.session.close()