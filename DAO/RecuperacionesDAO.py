import logging
from typing import Any, Dict, List, Optional, Tuple

from DAO.UsuariosDAO import get_conn
from models.recuperaciones import (
    EvidenciaCreateIn,
    ProveedorCreateIn,
    ProveedorUpdateIn,
    RecuperacionCreateIn,
)


# ── CATÁLOGOS ────────────────────────────────────────────────────────────────

def list_tipos_recuperacion() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT idTipoRecuperacion, Tipo FROM rec_tipos_recuperacion WHERE estatus=1 ORDER BY idTipoRecuperacion"
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return rows


# ── PROVEEDORES ───────────────────────────────────────────────────────────────

def list_proveedores(
    q: Optional[str],
    estatus: Optional[int],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if estatus is not None:
        where.append("estatus = %(estatus)s")
        params["estatus"] = estatus
    if q:
        where.append("proveedor LIKE %(q)s")
        params["q"] = f"%{q}%"

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    cur.execute(f"SELECT COUNT(*) AS total FROM rec_proveedores {where_sql}", params)
    total = int(cur.fetchone()["total"])

    cur.execute(
        f"""
        SELECT idProveedor, proveedor, estatus
        FROM rec_proveedores {where_sql}
        ORDER BY proveedor
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {**params, "limit": limit, "offset": offset},
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return rows, total


def get_proveedor(id_proveedor: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT idProveedor, proveedor, estatus FROM rec_proveedores WHERE idProveedor=%s",
        (id_proveedor,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    return row


def create_proveedor(data: ProveedorCreateIn) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO rec_proveedores (proveedor) VALUES (%s)",
        (data.proveedor,),
    )
    new_id = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return int(new_id)


def update_proveedor(id_proveedor: int, data: ProveedorUpdateIn) -> int:
    sets, params = [], []
    if data.proveedor is not None:
        sets.append("proveedor=%s"); params.append(data.proveedor)
    if data.estatus is not None:
        sets.append("estatus=%s"); params.append(data.estatus)
    if not sets:
        return 0
    params.append(id_proveedor)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE rec_proveedores SET {', '.join(sets)} WHERE idProveedor=%s", tuple(params))
    conn.commit(); ra = cur.rowcount
    cur.close(); conn.close()
    return ra


def baja_proveedor(id_proveedor: int) -> int:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE rec_proveedores SET estatus=0 WHERE idProveedor=%s AND estatus=1", (id_proveedor,))
    conn.commit(); ra = cur.rowcount
    cur.close(); conn.close()
    return ra


def asignar_proveedor_zona(id_proveedor: int, id_zona: int) -> int:
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT 1 FROM rec_proveedor_zona WHERE idProveedor=%s AND idZona=%s LIMIT 1",
        (id_proveedor, id_zona),
    )
    if cur.fetchone():
        cur.close(); conn.close()
        return 0  # ya existía
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO rec_proveedor_zona (idProveedor, idZona) VALUES (%s, %s)",
        (id_proveedor, id_zona),
    )
    new_id = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return int(new_id)


def list_proveedores_por_centro(id_centro: str) -> List[Dict[str, Any]]:
    """Proveedores activos disponibles para una sucursal (obtiene zona desde sucursales.idZona)."""
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT p.idProveedor, p.proveedor, p.estatus
        FROM rec_proveedores p
        JOIN rec_proveedor_zona rpz ON rpz.idProveedor = p.idProveedor
        JOIN zonas z                ON z.idZona        = rpz.idZona
        JOIN sucursales s           ON s.idZona        = z.idZona
        WHERE s.idCentro = %s AND p.estatus = 1
        ORDER BY p.proveedor
        """,
        (id_centro,),
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return rows


# ── RECUPERACIONES ────────────────────────────────────────────────────────────

def create_recuperacion(data: RecuperacionCreateIn) -> int:
    conn = get_conn()
    conn.autocommit = False  # forzar transacción explícita (Azure MySQL puede ignorar el CFG)
    cur = conn.cursor()
    try:
        # ── 1. Encabezado ──────────────────────────────────────────────────
        cur.execute(
            """
            INSERT INTO rec_recuperaciones
            (idCentro, idTipoRecuperacion, idProveedor, nombreInfractor,
             comentario, idUsuario, fechaHora, estatus)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 1)
            """,
            (
                data.idCentro,
                data.idTipoRecuperacion,
                data.idProveedor,
                data.nombreInfractor,
                data.comentario,
                data.idUsuario,
            ),
        )
        id_rec = cur.lastrowid
        if not id_rec:
            raise ValueError("No se pudo obtener el ID de la recuperación insertada")

        logging.info(
            "Recuperación encabezado insertado: id=%s, productos=%d",
            id_rec, len(data.productos),
        )

        # ── 2. Detalle (productos) ──────────────────────────────────────────
        if not data.productos:
            raise ValueError("La lista de productos no puede estar vacía")

        for prod in data.productos:
            logging.info(
                "  Insertando detalle: idRecuperacion=%s, CodigoBarras=%s, cantidad=%s",
                id_rec, prod.CodigoBarras, prod.cantidad,
            )
            cur.execute(
                """
                INSERT INTO rec_recuperacion_detalle
                    (idRecuperacion, CodigoBarras, cantidad)
                VALUES (%s, %s, %s)
                """,
                (id_rec, prod.CodigoBarras, float(prod.cantidad)),
            )
            if cur.rowcount != 1:
                raise ValueError(
                    f"No se insertó el detalle para CodigoBarras={prod.CodigoBarras}"
                )

        # ── 3. Commit único — ambas tablas o ninguna ────────────────────────
        conn.commit()
        logging.info("Recuperación %s registrada con %d productos", id_rec, len(data.productos))
    except Exception as exc:
        conn.rollback()
        logging.error("Error en create_recuperacion, rollback ejecutado: %s", exc)
        raise
    finally:
        cur.close(); conn.close()
    return int(id_rec)


def list_recuperaciones(
    id_centro: Optional[str],
    id_zona: Optional[int],
    id_tipo: Optional[int],
    id_proveedor: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
    id_usuario: Optional[int],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_conn(); cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("r.idCentro = %(idCentro)s"); params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s"); params["idZona"] = id_zona
    if id_tipo:
        where.append("r.idTipoRecuperacion = %(idTipo)s"); params["idTipo"] = id_tipo
    if id_proveedor:
        where.append("r.idProveedor = %(idProveedor)s"); params["idProveedor"] = id_proveedor
    if fecha_inicio:
        where.append("DATE(r.fechaHora) >= %(fechaInicio)s"); params["fechaInicio"] = fecha_inicio
    if fecha_fin:
        where.append("DATE(r.fechaHora) <= %(fechaFin)s"); params["fechaFin"] = fecha_fin
    if id_usuario:
        where.append("r.idUsuario = %(idUsuario)s"); params["idUsuario"] = id_usuario

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM rec_recuperaciones r
        JOIN sucursales s ON s.idCentro = r.idCentro
        LEFT JOIN zonas z ON z.idZona = s.idZona
        {where_sql}
        """,
        params,
    )
    total = int(cur.fetchone()["total"])

    cur.execute(
        f"""
        SELECT
            r.idRecuperacion, r.idCentro, s.Sucursales AS Sucursal,
            z.idZona, z.Zona,
            r.idTipoRecuperacion, t.Tipo,
            r.idProveedor, p.proveedor,
            r.nombreInfractor, r.comentario,
            r.idUsuario, u.NombreUsuario,
            r.fechaEvento, r.fechaRegistro, r.estatus,
            COUNT(d.idDetalle)                        AS totalProductos,
            COALESCE(SUM(d.cantidad * c.Precio), 0)  AS importeTotal
        FROM rec_recuperaciones r
        JOIN sucursales s ON s.idCentro = r.idCentro
        LEFT JOIN zonas z                     ON z.idZona          = s.idZona
        LEFT JOIN rec_tipos_recuperacion t    ON t.idTipoRecuperacion = r.idTipoRecuperacion
        LEFT JOIN rec_proveedores p           ON p.idProveedor      = r.idProveedor
        LEFT JOIN usuarios u                  ON u.IdUsuarios       = r.idUsuario
        LEFT JOIN rec_recuperacion_detalle d  ON d.idRecuperacion   = r.idRecuperacion
        LEFT JOIN catalogo c                  ON c.CodigoBarras     = d.CodigoBarras
        {where_sql}
        GROUP BY r.idRecuperacion
        ORDER BY r.fechaHora DESC, r.idRecuperacion DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {**params, "limit": limit, "offset": offset},
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return rows, total


def get_recuperacion_by_id(id_rec: int) -> Optional[Dict[str, Any]]:
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            r.idRecuperacion, r.idCentro, s.Sucursales AS Sucursal,
            z.idZona, z.Zona,
            r.idTipoRecuperacion, t.Tipo,
            r.idProveedor, p.proveedor,
            r.nombreInfractor, r.comentario,
            r.idUsuario, u.NombreUsuario,
            r.fechaEvento, r.fechaRegistro, r.estatus,
            COALESCE(SUM(d.cantidad * c.Precio), 0) AS importeTotal
        FROM rec_recuperaciones r
        JOIN sucursales s ON s.idCentro = r.idCentro
        LEFT JOIN zonas z                     ON z.idZona            = s.idZona
        LEFT JOIN rec_tipos_recuperacion t    ON t.idTipoRecuperacion = r.idTipoRecuperacion
        LEFT JOIN rec_proveedores p           ON p.idProveedor        = r.idProveedor
        LEFT JOIN usuarios u                  ON u.IdUsuarios         = r.idUsuario
        LEFT JOIN rec_recuperacion_detalle d  ON d.idRecuperacion     = r.idRecuperacion
        LEFT JOIN catalogo c                  ON c.CodigoBarras       = d.CodigoBarras
        WHERE r.idRecuperacion = %s
        GROUP BY r.idRecuperacion
        """,
        (id_rec,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    return row


def get_detalle_recuperacion(id_rec: int) -> List[Dict[str, Any]]:
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            d.idDetalle, d.CodigoBarras,
            c.Producto,
            d.cantidad,
            COALESCE(c.Precio, 0)                    AS precio,
            COALESCE(d.cantidad * c.Precio, 0)       AS importe
        FROM rec_recuperacion_detalle d
        LEFT JOIN catalogo c ON c.CodigoBarras = d.CodigoBarras
        WHERE d.idRecuperacion = %s
        ORDER BY d.idDetalle
        """,
        (id_rec,),
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return rows


def add_evidencia(id_rec: int, data: EvidenciaCreateIn) -> int:
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rec_evidencias (idRecuperacion, rutaArchivo, tipoArchivo, fechaRegistro, idUsuario)
        VALUES (%s, %s, %s, NOW(), %s)
        """,
        (id_rec, data.rutaArchivo, data.tipoArchivo, data.idUsuario),
    )
    new_id = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return int(new_id)


def update_estatus_recuperacion(id_rec: int, estatus: int) -> int:
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "UPDATE rec_recuperaciones SET estatus=%s WHERE idRecuperacion=%s",
        (estatus, id_rec),
    )
    conn.commit(); ra = cur.rowcount
    cur.close(); conn.close()
    return ra


# ── DASHBOARD / STATS ────────────────────────────────────────────────────────

def get_stats_recuperaciones(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
) -> Dict[str, Any]:
    conn = get_conn(); cur = conn.cursor(dictionary=True)

    where: List[str] = ["r.estatus = 1"]
    params: Dict[str, Any] = {}
    if id_centro:
        where.append("r.idCentro = %(idCentro)s"); params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s"); params["idZona"] = id_zona
    if fecha_inicio:
        where.append("DATE(r.fechaHora) >= %(fechaInicio)s"); params["fechaInicio"] = fecha_inicio
    if fecha_fin:
        where.append("DATE(r.fechaHora) <= %(fechaFin)s"); params["fechaFin"] = fecha_fin

    where_sql = f"WHERE {' AND '.join(where)}"

    base_join = """
        FROM rec_recuperaciones r
        JOIN sucursales s ON s.idCentro = r.idCentro
        LEFT JOIN zonas z ON z.idZona = s.idZona
        LEFT JOIN rec_recuperacion_detalle d ON d.idRecuperacion = r.idRecuperacion
        LEFT JOIN catalogo c ON c.CodigoBarras = d.CodigoBarras
    """

    # Totales generales
    cur.execute(
        f"SELECT COUNT(DISTINCT r.idRecuperacion) AS totalEventos, COALESCE(SUM(d.cantidad * c.Precio), 0) AS totalImporte {base_join} {where_sql}",
        params,
    )
    totales = cur.fetchone() or {}

    # Por zona
    cur.execute(
        f"""
        SELECT z.idZona, z.Zona,
               COUNT(DISTINCT r.idRecuperacion)          AS total,
               COALESCE(SUM(d.cantidad * c.Precio), 0)  AS importe
        {base_join} {where_sql}
        GROUP BY z.idZona, z.Zona ORDER BY importe DESC
        """,
        params,
    )
    por_zona = cur.fetchall() or []

    # Por sucursal
    cur.execute(
        f"""
        SELECT r.idCentro, s.Sucursales AS Sucursal,
               COUNT(DISTINCT r.idRecuperacion)          AS total,
               COALESCE(SUM(d.cantidad * c.Precio), 0)  AS importe
        {base_join} {where_sql}
        GROUP BY r.idCentro, s.Sucursales ORDER BY importe DESC LIMIT 20
        """,
        params,
    )
    por_sucursal = cur.fetchall() or []

    # Por proveedor
    cur.execute(
        f"""
        SELECT r.idProveedor, p.proveedor,
               COUNT(DISTINCT r.idRecuperacion)          AS total,
               COALESCE(SUM(d.cantidad * c.Precio), 0)  AS importe
        {base_join}
        LEFT JOIN rec_proveedores p ON p.idProveedor = r.idProveedor
        {where_sql}
        GROUP BY r.idProveedor, p.proveedor ORDER BY importe DESC LIMIT 10
        """,
        params,
    )
    por_proveedor = cur.fetchall() or []

    # Por tipo
    cur.execute(
        f"""
        SELECT r.idTipoRecuperacion, t.Tipo,
               COUNT(DISTINCT r.idRecuperacion)          AS total,
               COALESCE(SUM(d.cantidad * c.Precio), 0)  AS importe
        {base_join}
        LEFT JOIN rec_tipos_recuperacion t ON t.idTipoRecuperacion = r.idTipoRecuperacion
        {where_sql}
        GROUP BY r.idTipoRecuperacion, t.Tipo ORDER BY importe DESC
        """,
        params,
    )
    por_tipo = cur.fetchall() or []

    # Top productos
    cur.execute(
        f"""
        SELECT d.CodigoBarras, c.Producto,
               COALESCE(SUM(d.cantidad), 0)              AS totalCantidad,
               COALESCE(SUM(d.cantidad * c.Precio), 0)  AS importe
        {base_join} {where_sql}
        GROUP BY d.CodigoBarras, c.Producto ORDER BY importe DESC LIMIT 10
        """,
        params,
    )
    top_productos = cur.fetchall() or []

    # Por mes (últimos 12)
    cur.execute(
        f"""
        SELECT DATE_FORMAT(r.fechaHora, '%Y-%m') AS mes,
               COUNT(DISTINCT r.idRecuperacion)    AS total
        FROM rec_recuperaciones r
        JOIN sucursales s ON s.idCentro = r.idCentro
        LEFT JOIN zonas z ON z.idZona = s.idZona
        {where_sql}
        GROUP BY mes ORDER BY mes DESC LIMIT 12
        """,
        params,
    )
    por_mes = cur.fetchall() or []

    cur.close(); conn.close()
    return {
        "totalImporte": totales.get("totalImporte", 0),
        "totalEventos": int(totales.get("totalEventos", 0)),
        "porZona": por_zona,
        "porSucursal": por_sucursal,
        "porProveedor": por_proveedor,
        "porTipo": por_tipo,
        "topProductos": top_productos,
        "porMes": por_mes,
    }
