# dao/usuarios_dao.py
from __future__ import annotations

import mysql.connector as mysql
import os
from passlib.hash import bcrypt
# models/usuarios.py
from typing import Optional, Dict, List, Tuple, Any
from pydantic import BaseModel, Field, validator
from datetime import date

class UsuarioCreateIn(BaseModel):
    idUsuarios: int = Field(..., gt=0)
    NombreUsuario: str = Field(..., min_length=3, max_length=45)
    pwd: str = Field(..., min_length=8)  # min. 8 y combina (valida abajo)
    idNivelUsuario: int = Field(..., gt=0)
    estatus: int = Field(1)  # A/I o 1/0
    idCentro: str = Field(..., min_length=1, max_length=10)

    @validator("pwd")
    def strong_pwd(cls, v: str):
        # Reglas simples: 8+, al menos una letra y un dígito (ajusta si quieres symbols)
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe incluir letras y números")
        return v

class UsuarioCreatedOut(BaseModel):
    estatus: int
    mensaje: str
    usuario: Dict[str, object]

'mysql+pymysql://ecastillo:Cachopp2@mysql-met.mysql.database.azure.com:3306/scisp'

CFG = dict(
    host=os.getenv("DB_HOST","mysql-met.mysql.database.azure.com"),
    user=os.getenv("DB_USER","ecastillo"),
    password=os.getenv("DB_PASS","Cachopp2"),
    database=os.getenv("DB_NAME","scisp"),
    autocommit=False
)
#CFG = dict(
 #   host=os.getenv("DB_HOST","localhost"),
  #  user=os.getenv("DB_USER","root"),
   # password=os.getenv("DB_PASS","root"),
    #database=os.getenv("DB_NAME","scisp"),
    #autocommit=False
#)

def get_conn():
    return mysql.connect(**CFG)

def get_usuario_by_id(user_id: int):
    """
    Devuelve Estatus como 1 (activo) o 0 (inactivo), sin letras.
    """
    sql = """
      SELECT
        IdUsuarios,
        NombreUsuario,
        Contraseña,
        idNivelUsuario,
        CASE
          WHEN Estatus IN ('A','1',1) THEN 1
          ELSE 0
        END AS Estatus
      FROM usuarios
      WHERE IdUsuarios = %s
    """
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(sql, (user_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def is_usuario_en_centro(user_id: int, id_centro: str) -> bool:
    """
    Espera tabla: met_usuariosuc(idmet_UsuarioSuc, idUsuarios, idCentro)
    """
    sql = "SELECT 1 FROM met_usuariosuc WHERE idUsuarios=%s AND idCentro=%s LIMIT 1"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (user_id, id_centro))
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok

def check_password(plain: str, hashed: str) -> bool:
    # hashed debería venir ya con bcrypt (ej: $2b$12$...)
    try:
        return bcrypt.verify(plain, hashed)
    except Exception:
        # fallback: por si aún tienes contraseñas en claro (temporal)
        return plain == hashed

def nivel_exists(id_nivel: int) -> bool:
    # Tabla: nivelusuarios(IdNivelUsuario, NivelUsuario) — ajusta si difiere
    sql = "SELECT 1 FROM nivelusuarios WHERE IdNivelUsuario=%s LIMIT 1"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (id_nivel,))
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok

def sucursal_exists(id_centro: str) -> bool:
    sql = "SELECT 1 FROM sucursales WHERE idCentro = %s COLLATE utf8mb4_spanish2_ci LIMIT 1"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (id_centro,))
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok

def usuario_sucursal_exists(user_id: int, id_centro: str) -> bool:
    sql = "SELECT 1 FROM met_usuariosuc WHERE idUsuarios=%s AND idCentro=%s LIMIT 1"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (user_id, id_centro))
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok

def insert_usuario(idUsuarios: int, nombre: str, pwd_plain: str,
                   idNivelUsuario: int, estatus: int) -> date:
    pwd_hash = bcrypt.hash(pwd_plain)
    fecha = date.today()
    sql = """
      INSERT INTO usuarios
        (`IdUsuarios`, `NombreUsuario`, `Contraseña`, `idNivelUsuario`, `Estatus`, `FechaAlta`)
      VALUES (%s, %s, %s, %s, %s, %s)
    """
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (idUsuarios, nombre, pwd_hash, idNivelUsuario, int(estatus), fecha))
    conn.commit()
    cur.close(); conn.close()
    return fecha

def assign_usuario_sucursal(idUsuarios: int, idCentro: str) -> None:
    if usuario_sucursal_exists(idUsuarios, idCentro):
        return
    sql = "INSERT INTO met_usuariosuc (idUsuarios, idCentro) VALUES (%s, %s)"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (idUsuarios, idCentro))
    conn.commit()
    cur.close(); conn.close()

def user_exists(user_id: int) -> bool:
    conn = get_conn();
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM usuarios WHERE IdUsuarios=%s LIMIT 1", (user_id,))
    ok = cur.fetchone() is not None
    cur.close();
    conn.close()
    return ok

def update_usuario(
        user_id: int,
        nombre: Optional[str] = None,
        id_nivel: Optional[int] = None,
        estatus: Optional[int] = None
) -> int:
        """
        Actualiza columnas presentes. Devuelve rows-affected.
        """
        sets = []
        params = []
        if nombre is not None:
            sets.append("NombreUsuario=%s")
            params.append(nombre)
        if id_nivel is not None:
            sets.append("idNivelUsuario=%s")
            params.append(id_nivel)
        if estatus is not None:
            sets.append("Estatus=%s")
            params.append(int(estatus))

        if not sets:
            return 0

        params.append(user_id)
        sql = f"UPDATE usuarios SET {', '.join(sets)} WHERE IdUsuarios=%s"
        conn = get_conn();
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        conn.commit()
        ra = cur.rowcount
        cur.close();
        conn.close()
        return ra

def upsert_usuario_sucursal(user_id: int, id_centro: str) -> bool:
        """
        Garantiza que exista la relación usuario-centro (no duplica).
        Regresa True si insertó, False si ya existía.
        """
        if usuario_sucursal_exists(user_id, id_centro):
            return False
        conn = get_conn();
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO met_usuariosuc (idUsuarios, idCentro) VALUES (%s, %s)",
            (user_id, id_centro)
        )
        conn.commit()
        cur.close();
        conn.close()
        return True
def get_usuario_row(user_id: int) -> Optional[Dict]:
    """
    Trae al usuario tal cual de la BD (con Estatus 1/0).
    """
    sql = """
      SELECT
        IdUsuarios,
        NombreUsuario,
        idNivelUsuario,
        CASE WHEN Estatus IN ('A','1',1) THEN 1 ELSE 0 END AS Estatus,
        FechaAlta
      FROM usuarios
      WHERE IdUsuarios = %s
    """
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(sql, (user_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def get_nivel_info(id_nivel: int) -> Optional[Dict]:
    sql = """
      SELECT IdNivelUsuario, NivelUsuario
      FROM nivelusuarios
      WHERE IdNivelUsuario = %s
    """
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(sql, (id_nivel,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def get_sucursales_de_usuario(user_id: int) -> List[Dict]:
    # join a sucursales para nombre visible
    sql = """
      SELECT us.idCentro, s.Sucursales AS Sucursal
      FROM met_usuariosuc us
      JOIN sucursales s
        ON s.idCentro = us.idCentro COLLATE utf8mb4_spanish2_ci
      WHERE us.idUsuarios = %s
      ORDER BY us.idCentro
    """
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(sql, (user_id,))
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return rows

def insert_usuario_sucursal(user_id: int, id_centro: str) -> int:
    sql = "INSERT INTO met_usuariosuc (idUsuarios, idCentro) VALUES (%s, %s)"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (user_id, id_centro))
    conn.commit()
    ra = cur.rowcount
    cur.close(); conn.close()
    return ra

def get_usuario_estatus(user_id: int) -> int | None:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT Estatus FROM usuarios WHERE IdUsuarios=%s", (user_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return None if row is None else int(row[0])

def set_usuario_baja(user_id: int) -> int:
    """
    Pone Estatus=0 solo si no estaba ya en 0.
    Devuelve rowcount (0 si ya estaba en 0, 1 si se actualizó).
    """
    sql = "UPDATE usuarios SET Estatus=0 WHERE IdUsuarios=%s AND Estatus<>0"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (user_id,))
    conn.commit()
    rc = cur.rowcount
    cur.close(); conn.close()
    return rc
def usuario_existe(user_id: int) -> bool:
    """
        Valida existencia en 'usuarios' usando la columna real 'IdUsuarios'.
        """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM usuarios WHERE IdUsuarios = %s LIMIT 1", (user_id,))
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
    return ok


# UsuariosDAO.py


# ... (deja lo que ya tengas)

def list_usuarios(
    limit: int = 50,
    offset: int = 0,
    estatus: Optional[int] = None,
    idNivelUsuario: Optional[int] = None,
    q: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Devuelve (rows, total) con paginación y filtros.
    Incluye nombre del nivel y cantidad de sucursales asignadas.
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # --- filtros dinámicos (para ambas consultas) ---
    where = []
    params: Dict[str, Any] = {}

    if estatus is not None:
        where.append("u.Estatus = %(estatus)s")
        params["estatus"] = estatus

    if idNivelUsuario is not None:
        where.append("u.idNivelUsuario = %(idNivelUsuario)s")
        params["idNivelUsuario"] = idNivelUsuario

    if q:
        # busca por idUsuarios o coincidencia en nombre
        where.append("(u.IdUsuarios LIKE %(q)s OR u.NombreUsuario LIKE %(q)s)")
        params["q"] = f"%{q}%"

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    # --- total (sin joins pesados) ---
    sql_total = f"""
        SELECT COUNT(*) AS total
          FROM usuarios u
          {where_sql}
    """
    cur.execute(sql_total, params)
    total = int(cur.fetchone()["total"])

    # --- page (con nivel + conteo de sucursales) ---
    sql_page = f"""
        SELECT
            u.IdUsuarios         AS idUsuarios,
            u.NombreUsuario      AS NombreUsuario,
            u.idNivelUsuario     AS idNivelUsuario,
            u.Estatus            AS estatus,
            u.FechaAlta          AS FechaAlta,
            n.NivelUsuario       AS nivel,
            COALESCE(COUNT(us.idCentro), 0) AS sucursales
        FROM usuarios u
        LEFT JOIN nivelusuarios n
               ON n.IdNivelUsuario = u.idNivelUsuario
        LEFT JOIN met_usuariosuc us
               ON us.idUsuarios = u.IdUsuarios
        {where_sql}
        GROUP BY u.IdUsuarios
        ORDER BY u.IdUsuarios
        LIMIT %(limit)s OFFSET %(offset)s
    """
    params_page = {**params, "limit": limit, "offset": offset}
    cur.execute(sql_page, params_page)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows, total

# UsuariosDAO.py


