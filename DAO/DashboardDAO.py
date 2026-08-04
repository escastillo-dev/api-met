from decimal import Decimal
from typing import Any, Dict, List, Optional

from DAO.UsuariosDAO import get_conn


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fecha_where(alias: str, fecha_inicio: Optional[str], fecha_fin: Optional[str]) -> tuple:
    """Devuelve (fragmento SQL, params dict) para filtrar por rango de fechas."""
    parts: List[str] = []
    params: Dict[str, Any] = {}
    if fecha_inicio:
        parts.append(f"DATE({alias}) >= %(fechaInicio)s")
        params["fechaInicio"] = fecha_inicio
    if fecha_fin:
        parts.append(f"DATE({alias}) <= %(fechaFin)s")
        params["fechaFin"] = fecha_fin
    return (" AND ".join(parts), params)


# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN (KPIs)
# ─────────────────────────────────────────────────────────────────────────────

def get_resumen_merma(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("m.idCentro = %(idCentro)s")
        params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s")
        params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("m.Fecha", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql)
        params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    cur.execute(
        f"""
        SELECT
            COUNT(DISTINCT m.idMaMe)                        AS totalEventos,
            COALESCE(SUM(d.Cantidad * c.Precio), 0)         AS totalImporte
        FROM met_mame m
        LEFT JOIN sucursales s   ON s.idCentro = m.idCentro
        LEFT JOIN zonas z        ON z.idZona   = s.idZona
        LEFT JOIN met_detmame d  ON d.idMaMe   = m.idMaMe
        LEFT JOIN catalogo c     ON c.CodigoBarras = d.CodigoBarras
        {where_sql}
        """,
        params,
    )
    row = cur.fetchone() or {}
    cur.close(); conn.close()
    return {
        "totalEventos": int(row.get("totalEventos") or 0),
        "totalImporte": Decimal(str(row.get("totalImporte") or 0)),
    }


def get_resumen_recuperaciones(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("r.idCentro = %(idCentro)s")
        params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s")
        params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("r.fechaHora", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql)
        params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    cur.execute(
        f"""
        SELECT
            COUNT(DISTINCT r.idRecuperacion)                AS totalEventos,
            COALESCE(SUM(d.cantidad * c.Precio), 0)         AS totalImporte
        FROM rec_recuperaciones r
        LEFT JOIN sucursales s              ON s.idCentro = r.idCentro
        LEFT JOIN zonas z                   ON z.idZona   = s.idZona
        LEFT JOIN rec_recuperacion_detalle d ON d.idRecuperacion = r.idRecuperacion
        LEFT JOIN catalogo c                ON c.CodigoBarras = d.CodigoBarras
        {where_sql}
        """,
        params,
    )
    row = cur.fetchone() or {}
    cur.close(); conn.close()
    return {
        "totalEventos": int(row.get("totalEventos") or 0),
        "totalImporte": Decimal(str(row.get("totalImporte") or 0)),
    }


def get_resumen_caducidad(
    id_centro: Optional[str],
    id_zona: Optional[int],
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = ["1=1"]
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("r.idCentro = %(idCentro)s")
        params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s")
        params["idZona"] = id_zona

    where_sql = " AND ".join(where)

    # Si hay filtro de zona necesitamos join a sucursales/zonas
    join_zona = ""
    if id_zona:
        join_zona = """
            JOIN sucursales s ON s.idCentro = r.idCentro
            JOIN zonas z      ON z.idZona   = s.idZona
        """

    cur.execute(
        f"""
        SELECT
            SUM(CASE WHEN r.estatus = 'A' AND DATEDIFF(r.fechaCaducidad, CURDATE()) <= 7            THEN 1 ELSE 0 END) AS criticos,
            SUM(CASE WHEN r.estatus = 'A' AND DATEDIFF(r.fechaCaducidad, CURDATE()) BETWEEN 8  AND 15 THEN 1 ELSE 0 END) AS urgentes,
            SUM(CASE WHEN r.estatus = 'A' AND DATEDIFF(r.fechaCaducidad, CURDATE()) BETWEEN 16 AND 30 THEN 1 ELSE 0 END) AS proximos,
            SUM(CASE WHEN r.estatus = 'C'                                                            THEN 1 ELSE 0 END) AS cerrados
        FROM met_cad_registros r
        {join_zona}
        WHERE {where_sql}
        """,
        params,
    )
    row = cur.fetchone() or {}
    cur.close(); conn.close()
    return {
        "criticos": int(row.get("criticos") or 0),
        "urgentes": int(row.get("urgentes") or 0),
        "proximos": int(row.get("proximos") or 0),
        "cerrados": int(row.get("cerrados") or 0),
    }


def get_resumen_manejo_valores(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("mv.idCentro = %(idCentro)s")
        params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s")
        params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("mv.Fecha", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql)
        params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    join_zona = ""
    if id_zona:
        join_zona = """
            JOIN sucursales s ON s.idCentro = mv.idCentro
            JOIN zonas z      ON z.idZona   = s.idZona
        """

    cur.execute(
        f"""
        SELECT
            SUM(CASE WHEN mv.Estado = 'A' THEN 1 ELSE 0 END) AS foliosAbiertos,
            SUM(CASE WHEN mv.Estado = 'C' THEN 1 ELSE 0 END) AS foliosCerrados,
            COUNT(*)                                           AS totalMovimientos
        FROM met_manejovalores mv
        {join_zona}
        {where_sql}
        """,
        params,
    )
    row = cur.fetchone() or {}
    cur.close(); conn.close()
    return {
        "foliosAbiertos":  int(row.get("foliosAbiertos")  or 0),
        "foliosCerrados":  int(row.get("foliosCerrados")  or 0),
        "totalMovimientos": int(row.get("totalMovimientos") or 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICAS
# ─────────────────────────────────────────────────────────────────────────────

def get_merma_vs_recuperaciones(
    id_centro: Optional[str],
    id_zona: Optional[int],
    meses: int = 6,
) -> List[Dict[str, Any]]:
    """Comparativo mensual merma vs recuperaciones (últimos N meses)."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    centro_filter_m  = "AND m.idCentro = %(idCentro)s" if id_centro else ""
    centro_filter_r  = "AND r.idCentro = %(idCentro)s" if id_centro else ""
    zona_join_m      = "JOIN sucursales s ON s.idCentro = m.idCentro JOIN zonas z ON z.idZona = s.idZona" if id_zona else ""
    zona_join_r      = "JOIN sucursales s ON s.idCentro = r.idCentro JOIN zonas z ON z.idZona = s.idZona" if id_zona else ""
    zona_filter      = "AND z.idZona = %(idZona)s" if id_zona else ""

    params: Dict[str, Any] = {"meses": meses}
    if id_centro:
        params["idCentro"] = id_centro
    if id_zona:
        params["idZona"] = id_zona

    cur.execute(
        f"""
        SELECT mes,
               MAX(merma)         AS merma,
               MAX(recuperaciones) AS recuperaciones
        FROM (
            SELECT DATE_FORMAT(m.Fecha, '%Y-%m') AS mes,
                   COALESCE(SUM(d.Cantidad * c.Precio), 0) AS merma,
                   0 AS recuperaciones
            FROM met_mame m
            {zona_join_m}
            LEFT JOIN met_detmame d  ON d.idMaMe       = m.idMaMe
            LEFT JOIN catalogo c     ON c.CodigoBarras  = d.CodigoBarras
            WHERE m.Fecha >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %(meses)s MONTH), '%Y-%m-01')
              {centro_filter_m} {zona_filter}
            GROUP BY DATE_FORMAT(m.Fecha, '%Y-%m')

            UNION ALL

            SELECT DATE_FORMAT(r.fechaHora, '%Y-%m') AS mes,
                   0 AS merma,
                   COALESCE(SUM(det.cantidad * c.Precio), 0) AS recuperaciones
            FROM rec_recuperaciones r
            {zona_join_r}
            LEFT JOIN rec_recuperacion_detalle det ON det.idRecuperacion = r.idRecuperacion
            LEFT JOIN catalogo c                   ON c.CodigoBarras     = det.CodigoBarras
            WHERE r.fechaHora >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL %(meses)s MONTH), '%Y-%m-01')
              {centro_filter_r} {zona_filter}
            GROUP BY DATE_FORMAT(r.fechaHora, '%Y-%m')
        ) t
        GROUP BY mes
        ORDER BY mes ASC
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return [
        {
            "mes": r["mes"],
            "merma": Decimal(str(r["merma"] or 0)),
            "recuperaciones": Decimal(str(r["recuperaciones"] or 0)),
        }
        for r in rows
    ]


def get_top_productos_merma(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
    top: int = 10,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {"top": top}

    if id_centro:
        where.append("m.idCentro = %(idCentro)s"); params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s"); params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("m.Fecha", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql); params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    join_zona = "JOIN sucursales s ON s.idCentro = m.idCentro JOIN zonas z ON z.idZona = s.idZona" if id_zona else ""

    cur.execute(
        f"""
        SELECT d.CodigoBarras, c.Producto,
               COALESCE(SUM(d.Cantidad), 0)              AS totalCantidad,
               COALESCE(SUM(d.Cantidad * c.Precio), 0)   AS importe
        FROM met_mame m
        {join_zona}
        JOIN met_detmame d ON d.idMaMe = m.idMaMe
        LEFT JOIN catalogo c ON c.CodigoBarras = d.CodigoBarras
        {where_sql}
        GROUP BY d.CodigoBarras, c.Producto
        ORDER BY importe DESC
        LIMIT %(top)s
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return [
        {
            "CodigoBarras": r["CodigoBarras"],
            "Producto": r["Producto"],
            "totalCantidad": Decimal(str(r["totalCantidad"] or 0)),
            "importe": Decimal(str(r["importe"] or 0)),
        }
        for r in rows
    ]


def get_top_productos_recuperacion(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
    top: int = 10,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {"top": top}

    if id_centro:
        where.append("r.idCentro = %(idCentro)s"); params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s"); params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("r.fechaHora", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql); params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    join_zona = "JOIN sucursales s ON s.idCentro = r.idCentro JOIN zonas z ON z.idZona = s.idZona" if id_zona else ""

    cur.execute(
        f"""
        SELECT d.CodigoBarras, c.Producto,
               COALESCE(SUM(d.cantidad), 0)              AS totalCantidad,
               COALESCE(SUM(d.cantidad * c.Precio), 0)   AS importe
        FROM rec_recuperaciones r
        {join_zona}
        JOIN rec_recuperacion_detalle d ON d.idRecuperacion = r.idRecuperacion
        LEFT JOIN catalogo c            ON c.CodigoBarras   = d.CodigoBarras
        {where_sql}
        GROUP BY d.CodigoBarras, c.Producto
        ORDER BY importe DESC
        LIMIT %(top)s
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return [
        {
            "CodigoBarras": r["CodigoBarras"],
            "Producto": r["Producto"],
            "totalCantidad": Decimal(str(r["totalCantidad"] or 0)),
            "importe": Decimal(str(r["importe"] or 0)),
        }
        for r in rows
    ]


def get_caducidad_por_zona(
    id_centro: Optional[str],
) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = ["r.estatus = 'A'"]
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("r.idCentro = %(idCentro)s"); params["idCentro"] = id_centro

    where_sql = " AND ".join(where)

    cur.execute(
        f"""
        SELECT z.idZona, z.Zona,
               SUM(CASE WHEN DATEDIFF(r.fechaCaducidad, CURDATE()) <= 7            THEN 1 ELSE 0 END) AS criticos,
               SUM(CASE WHEN DATEDIFF(r.fechaCaducidad, CURDATE()) BETWEEN 8  AND 15 THEN 1 ELSE 0 END) AS urgentes,
               SUM(CASE WHEN DATEDIFF(r.fechaCaducidad, CURDATE()) BETWEEN 16 AND 30 THEN 1 ELSE 0 END) AS proximos
        FROM met_cad_registros r
        JOIN sucursales s ON s.idCentro = r.idCentro
        JOIN zonas z      ON z.idZona   = s.idZona
        WHERE {where_sql}
        GROUP BY z.idZona, z.Zona
        ORDER BY (criticos + urgentes) DESC
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return [
        {
            "idZona": r["idZona"],
            "Zona": r["Zona"],
            "criticos": int(r["criticos"] or 0),
            "urgentes": int(r["urgentes"] or 0),
            "proximos": int(r["proximos"] or 0),
        }
        for r in rows
    ]


def get_merma_por_motivo(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("m.idCentro = %(idCentro)s"); params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s"); params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("m.Fecha", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql); params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    join_zona = "JOIN sucursales s ON s.idCentro = m.idCentro JOIN zonas z ON z.idZona = s.idZona" if id_zona else ""

    cur.execute(
        f"""
        SELECT mot.idMotMer, mot.Motivo,
               COUNT(DISTINCT m.idMaMe)                  AS totalEventos,
               COALESCE(SUM(d.Cantidad * c.Precio), 0)   AS importe
        FROM met_mame m
        {join_zona}
        JOIN met_detmame d      ON d.idMaMe       = m.idMaMe
        JOIN met_motmerma mot   ON mot.idMotMer    = d.idMotMer
        LEFT JOIN catalogo c    ON c.CodigoBarras  = d.CodigoBarras
        {where_sql}
        GROUP BY mot.idMotMer, mot.Motivo
        ORDER BY importe DESC
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return [
        {
            "idMotMer": r["idMotMer"],
            "Motivo": r["Motivo"],
            "totalEventos": int(r["totalEventos"] or 0),
            "importe": Decimal(str(r["importe"] or 0)),
        }
        for r in rows
    ]


def get_recuperacion_por_tipo(
    id_centro: Optional[str],
    id_zona: Optional[int],
    fecha_inicio: Optional[str],
    fecha_fin: Optional[str],
) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    where: List[str] = []
    params: Dict[str, Any] = {}

    if id_centro:
        where.append("r.idCentro = %(idCentro)s"); params["idCentro"] = id_centro
    if id_zona:
        where.append("z.idZona = %(idZona)s"); params["idZona"] = id_zona

    fecha_sql, fecha_params = _fecha_where("r.fechaHora", fecha_inicio, fecha_fin)
    if fecha_sql:
        where.append(fecha_sql); params.update(fecha_params)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    join_zona = "JOIN sucursales s ON s.idCentro = r.idCentro JOIN zonas z ON z.idZona = s.idZona" if id_zona else ""

    cur.execute(
        f"""
        SELECT t.idTipoRecuperacion, t.Tipo,
               COUNT(DISTINCT r.idRecuperacion)           AS totalEventos,
               COALESCE(SUM(d.cantidad * c.Precio), 0)   AS importe
        FROM rec_recuperaciones r
        {join_zona}
        JOIN rec_tipos_recuperacion t       ON t.idTipoRecuperacion = r.idTipoRecuperacion
        LEFT JOIN rec_recuperacion_detalle d ON d.idRecuperacion    = r.idRecuperacion
        LEFT JOIN catalogo c                ON c.CodigoBarras       = d.CodigoBarras
        {where_sql}
        GROUP BY t.idTipoRecuperacion, t.Tipo
        ORDER BY importe DESC
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close(); conn.close()
    return [
        {
            "idTipoRecuperacion": r["idTipoRecuperacion"],
            "Tipo": r["Tipo"],
            "totalEventos": int(r["totalEventos"] or 0),
            "importe": Decimal(str(r["importe"] or 0)),
        }
        for r in rows
    ]
