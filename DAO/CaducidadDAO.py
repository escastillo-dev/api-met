from typing import Any, Dict, List, Optional, Tuple

from DAO.UsuariosDAO import get_conn
from models.caducidad import CadAccionCreateIn, CadCierreCreateIn, CadRegistroCreateIn


def get_cad_resumen(id_centro: Optional[str] = None) -> Dict[str, int]:
    """
    Devuelve conteos para el dashboard:
      - criticos:  abiertos con diasRestantes <= 7
      - urgentes:  abiertos con diasRestantes entre 8 y 15
      - proximos:  abiertos con diasRestantes entre 16 y 30
      - cerrados:  estatus = 'C'
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    filtro = "AND idCentro = %s" if id_centro else ""
    params = (id_centro,) if id_centro else ()

    cur.execute(
        f"""
        SELECT
            SUM(CASE WHEN estatus = 'A' AND DATEDIFF(fechaCaducidad, CURDATE()) <= 7  THEN 1 ELSE 0 END) AS criticos,
            SUM(CASE WHEN estatus = 'A' AND DATEDIFF(fechaCaducidad, CURDATE()) BETWEEN 8  AND 15 THEN 1 ELSE 0 END) AS urgentes,
            SUM(CASE WHEN estatus = 'A' AND DATEDIFF(fechaCaducidad, CURDATE()) BETWEEN 16 AND 30 THEN 1 ELSE 0 END) AS proximos,
            SUM(CASE WHEN estatus = 'C' THEN 1 ELSE 0 END) AS cerrados
        FROM met_cad_registros
        WHERE 1=1 {filtro}
        """,
        params,
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "criticos":  int(row["criticos"]  or 0),
        "urgentes":  int(row["urgentes"]  or 0),
        "proximos":  int(row["proximos"]  or 0),
        "cerrados":  int(row["cerrados"]  or 0),
    }


def _sucursal_existe(id_centro: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sucursales WHERE idCentro=%s LIMIT 1", (id_centro,))
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
    return ok


def _usuario_existe(id_usuario: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM usuarios WHERE IdUsuarios=%s LIMIT 1", (id_usuario,))
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
    return ok


def _producto_existe(codigo_barras: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM catalogo WHERE CodigoBarras=%s LIMIT 1", (codigo_barras,))
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
    return ok


def _tipo_accion_existe(id_tipo_accion: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    ok = False
    try:
        cur.execute("SELECT 1 FROM met_cad_tipoacciones WHERE idAccionCad=%s LIMIT 1", (id_tipo_accion,))
        ok = cur.fetchone() is not None
    except Exception:
        try:
            cur.execute("SELECT 1 FROM met_cad_acciones WHERE idAccionCad=%s LIMIT 1", (id_tipo_accion,))
            ok = cur.fetchone() is not None
        except Exception:
            ok = False
    cur.close()
    conn.close()
    return ok


def create_cad_registro(data: CadRegistroCreateIn) -> int:
    if not _sucursal_existe(data.idCentro):
        raise ValueError("Sucursal no existe")
    if not _usuario_existe(data.idUsuarios):
        raise ValueError("Usuario de registro no existe")
    if not _producto_existe(data.CodigoBarras):
        raise ValueError("Producto no existe en catálogo")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO met_cad_registros
        (
            idCentro,
            CodigoBarras,
            fechaCaducidad,
            cantidadDetectada,
            FechaRegistro,
            idUsuarios,
            diasAlerta,
            estatus,
            nota
        )
        VALUES (%s, %s, %s, %s, NOW(), %s, %s, 'A', %s)
        """,
        (
            data.idCentro,
            data.CodigoBarras,
            data.fechaCaducidad,
            data.cantidadDetectada,
            data.idUsuarios,
            data.diasAlerta,
            data.nota,
        ),
    )
    new_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return int(new_id)


def list_cad_registros(
    estatus: Optional[str],
    id_centro: Optional[str],
    q: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if estatus:
        where.append("r.estatus = %(estatus)s")
        params["estatus"] = estatus
    if id_centro:
        where.append("r.idCentro = %(idCentro)s")
        params["idCentro"] = id_centro
    if q:
        where.append("(r.CodigoBarras LIKE %(q)s OR c.Producto LIKE %(q)s)")
        params["q"] = f"%{q}%"

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM met_cad_registros r
        LEFT JOIN catalogo c ON c.CodigoBarras = r.CodigoBarras
        {where_sql}
        """,
        params,
    )
    total = int(cur.fetchone()["total"])

    cur.execute(
        f"""
        SELECT
            r.idCad,
            r.idCentro,
            r.CodigoBarras,
            r.fechaCaducidad,
            r.cantidadDetectada,
            r.FechaRegistro,
            r.idUsuarios,
            r.diasAlerta,
            r.estatus,
            r.nota,
            DATEDIFF(r.fechaCaducidad, CURDATE()) AS diasRestantes,
            (
                SELECT MAX(a.fechaHora)
                FROM met_cad_acciones a
                WHERE a.idCad = r.idCad
            ) AS ultimaAccion
        FROM met_cad_registros r
        LEFT JOIN catalogo c ON c.CodigoBarras = r.CodigoBarras
        {where_sql}
        ORDER BY r.fechaCaducidad ASC, r.idCad DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    rows = cur.fetchall() or []

    cur.close()
    conn.close()
    return rows, total


def get_cad_registro_by_id(id_cad: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            idCad,
            idCentro,
            CodigoBarras,
            fechaCaducidad,
            cantidadDetectada,
            FechaRegistro,
            idUsuarios,
            diasAlerta,
            estatus,
            nota,
            DATEDIFF(fechaCaducidad, CURDATE()) AS diasRestantes
        FROM met_cad_registros
        WHERE idCad = %s
        """,
        (id_cad,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def list_cad_acciones(id_cad: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            idAccion,
            idCad,
            fechaHora,
            idTipoAccion,
            cantidad,
            resultado,
            comentario,
            idUsuarios
        FROM met_cad_acciones
        WHERE idCad = %s
        ORDER BY fechaHora DESC, idAccion DESC
        """,
        (id_cad,),
    )
    rows = cur.fetchall() or []
    cur.close()
    conn.close()
    return rows


def get_cad_cierre(id_cad: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            idCierre,
            idCad,
            fechaCierre,
            resultadoFinal,
            cantidadSalida,
            cantidadMerma,
            comentario,
            idUsuarios
        FROM met_cad_cierres
        WHERE idCad = %s
        LIMIT 1
        """,
        (id_cad,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def create_cad_accion(id_cad: int, data: CadAccionCreateIn) -> int:
    registro = get_cad_registro_by_id(id_cad)
    if not registro:
        raise ValueError("Caso no existe")
    if registro["estatus"] != "A":
        raise ValueError("El caso ya está cerrado")
    if not _usuario_existe(data.id_usuario_resuelto):
        raise ValueError("Usuario no existe")

    tipo_ok = _tipo_accion_existe(data.idTipoAccion)
    if not tipo_ok:
        raise ValueError("Tipo de acción no existe")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO met_cad_acciones
        (
            idCad,
            fechaHora,
            idTipoAccion,
            cantidad,
            resultado,
            comentario,
            idUsuarios
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
        """,
        (
            id_cad,
            data.idTipoAccion,
            data.cantidad,
            data.resultado,
            data.comentario,
            data.id_usuario_resuelto,
        ),
    )
    new_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return int(new_id)


def close_cad_registro(id_cad: int, data: CadCierreCreateIn) -> int:
    registro = get_cad_registro_by_id(id_cad)
    if not registro:
        raise ValueError("Caso no existe")
    if registro["estatus"] != "A":
        raise ValueError("El caso ya está cerrado")
    if not _usuario_existe(data.idUsuarios):
        raise ValueError("Usuario de cierre no existe")

    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT 1 FROM met_cad_cierres WHERE idCad=%s LIMIT 1", (id_cad,))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise ValueError("El caso ya tiene cierre")

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO met_cad_cierres
        (
            idCad,
            fechaCierre,
            resultadoFinal,
            cantidadSalida,
            cantidadMerma,
            comentario,
            idUsuarios
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
        """,
        (
            id_cad,
            data.resultadoFinal,
            data.cantidadSalida,
            data.cantidadMerma,
            data.comentario,
            data.idUsuarios,
        ),
    )
    id_cierre = cur.lastrowid

    cur.execute("UPDATE met_cad_registros SET estatus='C' WHERE idCad=%s", (id_cad,))

    conn.commit()
    cur.close()
    conn.close()
    return int(id_cierre)
