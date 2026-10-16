from typing import Any, Dict, List, Optional, Tuple

from DAO.UsuariosDAO import get_conn
from models.consumo import ProdConsumidoCreateIn


def _sucursal_existe(id_centro: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sucursales WHERE IdCentro=%s LIMIT 1", (id_centro,))
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


def crear_prodconsumido(data: ProdConsumidoCreateIn) -> Dict[str, Any]:
    """Inserta un registro en met_prodconsumidos. El Folio no se almacena
    en la tabla: se calcula a partir del idProdConsumido, tanto aquí (para
    la respuesta inmediata) como en la vista vw_met_prodconsumidos (para
    las lecturas posteriores).

    idColaborador es solo el número de nómina capturado (no tiene FK a
    ninguna tabla, no se valida existencia ni se conoce su nombre).
    """
    if not _sucursal_existe(data.idCentro):
        raise ValueError("Sucursal no existe")
    if not _usuario_existe(data.idUsuario):
        raise ValueError("Usuario de registro no existe")
    if not _producto_existe(data.CodigoBarras):
        raise ValueError("Producto no existe en catálogo")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO met_prodconsumidos
        (
            idCentro,
            idColaborador,
            CodigoBarras,
            Cantidad,
            idUsuario,
            Comentario
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            data.idCentro,
            data.idColaborador,
            data.CodigoBarras,
            data.Cantidad,
            data.idUsuario,
            data.Comentario,
        ),
    )
    new_id = cur.lastrowid
    folio = f"PC{new_id:08d}"
    conn.commit()

    cur.close()
    conn.close()
    return {"idProdConsumido": int(new_id), "Folio": folio}


def list_prodconsumidos(
    id_centro: Optional[str],
    id_colaborador: Optional[int],
    q: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if id_centro:
        where.append("p.idCentro = %(idCentro)s")
        params["idCentro"] = id_centro
    if id_colaborador:
        where.append("p.idColaborador = %(idColaborador)s")
        params["idColaborador"] = id_colaborador
    if q:
        where.append("(p.Folio COLLATE utf8mb4_general_ci LIKE %(q)s OR p.CodigoBarras LIKE %(q)s OR c.Producto LIKE %(q)s)")
        params["q"] = f"%{q}%"

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM vw_met_prodconsumidos p
        LEFT JOIN catalogo c ON c.CodigoBarras = p.CodigoBarras
        {where_sql}
        """,
        params,
    )
    total = int(cur.fetchone()["total"])

    cur.execute(
        f"""
        SELECT
            p.idProdConsumido,
            p.Folio,
            p.idCentro,
            p.idColaborador,
            p.CodigoBarras,
            p.Cantidad,
            p.idUsuario,
            p.FechaRegistro,
            p.Comentario,
            COALESCE(c.Producto, 'Producto no encontrado') AS nombreProducto,
            COALESCE(s.Sucursales, 'Sin nombre') AS nombreSucursal
        FROM vw_met_prodconsumidos p
        LEFT JOIN catalogo c ON c.CodigoBarras = p.CodigoBarras
        LEFT JOIN sucursales s ON s.IdCentro = p.idCentro
        {where_sql}
        ORDER BY p.FechaRegistro DESC, p.idProdConsumido DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    rows = cur.fetchall() or []

    cur.close()
    conn.close()
    return rows, total


def get_prodconsumido_by_folio(folio: str) -> Optional[Dict[str, Any]]:
    """Consulta usada por el guardia para verificar un producto marcado."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            p.idProdConsumido,
            p.Folio,
            p.idCentro,
            p.idColaborador,
            p.CodigoBarras,
            p.Cantidad,
            p.idUsuario,
            p.FechaRegistro,
            p.Comentario,
            COALESCE(c.Producto, 'Producto no encontrado') AS nombreProducto,
            COALESCE(s.Sucursales, 'Sin nombre') AS nombreSucursal
        FROM vw_met_prodconsumidos p
        LEFT JOIN catalogo c ON c.CodigoBarras = p.CodigoBarras
        LEFT JOIN sucursales s ON s.IdCentro = p.idCentro
        WHERE p.Folio COLLATE utf8mb4_general_ci = %s
        """,
        (folio,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row
