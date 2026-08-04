# dao/ManejoValoresDAO.py
from typing import Optional, Tuple, List, Dict
from datetime import datetime, date
from mysql.connector import connect
from DAO.UsuariosDAO import get_conn  # reutiliza tu get_conn()

def sucursal_existe(id_centro: str) -> bool:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT 1 FROM sucursales WHERE idCentro=%s LIMIT 1", (id_centro,))
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok

def usuario_activo(id_usuarios: int) -> bool:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT Estatus FROM usuarios WHERE IdUsuarios=%s", (id_usuarios,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row is None:
        return False
    # activo si 1 o 'A'
    val = row[0]
    try:
        return int(val) == 1
    except:
        return str(val).upper() == 'A'

def folio_abierto_hoy(id_centro: str) -> Optional[int]:
    sql = """
      SELECT Folio
      FROM met_manejovalores
      WHERE idCentro=%s AND Fecha=CURDATE() AND Estado='A'
      LIMIT 1
    """
    conn = get_conn(); cur = conn.cursor()
    cur.execute(sql, (id_centro,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return None if row is None else int(row[0])

def call_sp_abrir_folio(
    id_centro: str,
    anfitrion: int,
    id_usuarios: int,
    estado: str = 'A'
) -> int:
    """
    Llama al SP mmv_abrir_folio.
    Busca el folio abierto de HOY para idCentro; si no existe, crea el
    encabezado en met_manejovalores y devuelve el nuevo folio (OUT pFolio).
    """
    conn = get_conn(); cur = conn.cursor()
    args = (id_centro, anfitrion, id_usuarios, estado, 0)  # último = OUT pFolio
    result_args = cur.callproc('mmv_abrir_folio', args)
    conn.commit()
    folio = result_args[-1]
    cur.close(); conn.close()
    return int(folio)

def call_sp_insertar_manval(
    id_centro: str,
    anfitrion: int,
    id_usuarios: int,
    estado: str,          # 'A' para encabezado abierto
    movimiento: str,      # 'A' = Apertura
    hora_m: Optional[str],
    caja: int,
    cajero: int,
    id_incidencia: int,
    deposito: str,        # 'S' | 'N'
    comentario: Optional[str],
    sf: str,              # 'S' | 'N'
    tipo_sf: str,
    sf_monto: Optional[float]
) -> Tuple[str, Optional[int], Optional[int]]:
    """
    Llama al SP InsertarManVal. Devuelve (mensaje, folio, detId) si es posible.
    El SP setea pMsg; extraemos folio/detalle del texto cuando venga en el msg.
    """
    conn = get_conn(); cur = conn.cursor()

    # OUT param inicial
    pMsg = ""

    args = [
        id_centro,         # pSucursal
        anfitrion,         # pAnfitrion
        id_usuarios,       # pIdUsuarios
        estado,            # pEstado
        movimiento,        # pMovimiento
        hora_m,            # pHoraM
        caja,              # pCaja
        cajero,            # pCajero
        id_incidencia,     # pIdIncidencia
        deposito,          # pDeposito
        comentario,        # pComentario
        sf,                # pSF
        tipo_sf,           # pTipoSF
        sf_monto,          # pSFMonto
        pMsg               # OUT pMsg
    ]

    # mysql-connector-python actualiza args[-1] con el OUT param
    cur.callproc('InsertarManVal', args)

    # OUT param queda en args[-1]
    sp_msg = args[-1] if args and isinstance(args[-1], str) else ''
    conn.commit()
    cur.close(); conn.close()

    # Intentar extraer folio y detalle del mensaje "Movimiento registrado. Folio=X Detalle=Y"
    folio = None; det = None
    if sp_msg:
        try:
            # muy simple parseo
            parts = sp_msg.replace(',', ' ').replace('=', ' ').split()
            if 'Folio' in parts:
                folio = int(parts[parts.index('Folio') + 1])
            if 'Detalle' in parts:
                det = int(parts[parts.index('Detalle') + 1])
        except:
            pass

    return sp_msg, folio, det
def incidencia_existe(id_incidencia: int) -> bool:
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT 1 FROM met_incmanval WHERE idIncidencia=%s LIMIT 1", (id_incidencia,))
    ok = cur.fetchone() is not None
    cur.close(); conn.close()
    return ok

def call_sp_registrar_movimiento(
    folio: int,
    movimiento: str,       # 'R'|'C'|'A'
    hora_m: Optional[str],
    caja: int,
    cajero: int,
    id_incidencia: int,
    deposito: str,         # 'S'|'N'
    comentario: Optional[str],
    sf: str,               # 'S'|'N'
    tipo_sf: str,
    sf_monto: Optional[float]
) -> int:
    """
    Llama al SP mmv_registrar_mov. Requiere un folio YA abierto (Estado='A').
    El propio SP valida movimiento/folio/incidencia con SIGNAL SQLSTATE '45000',
    por lo que los errores llegan como mysql.connector.errors.Error (errno 1644)
    con un mensaje claro (p.ej. "Folio no existe o no está abierto").
    Devuelve el idDetManVal (OUT pDetId).
    """
    conn = get_conn(); cur = conn.cursor()
    args = (
        folio, movimiento, hora_m, caja, cajero, id_incidencia,
        deposito, comentario, sf, tipo_sf, sf_monto, 0  # último = OUT pDetId
    )
    result_args = cur.callproc('mmv_registrar_mov', args)
    conn.commit()
    det_id = result_args[-1]
    cur.close(); conn.close()
    return int(det_id)

def get_movimientos_generales(
    id_centro: Optional[str] = None,
    fecha: Optional[date] = None,
    folio: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[int, List[Dict]]:
    """
    Lee de la vista vMovimientos con filtros opcionales y paginación.
    Devuelve (total, rows)
    """
    where = []
    params: List = []

    if id_centro:
        # la vista ya trae 'Sucursales' y no 'idCentro'; filtramos por folio si lo pides
        # o usamos un subfiltro contra manejovalores si hace falta
        where.append("Folio IN (SELECT Folio FROM met_manejovalores WHERE idCentro=%s)")
        params.append(id_centro)

    if fecha:
        where.append("Fecha = %s")
        params.append(fecha)

    if folio:
        where.append("Folio = %s")
        params.append(folio)

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    sql_data = f"""
      SELECT
        Folio, Sucursales, Fecha, Movimiento,
        TIME_FORMAT(Hora, '%H:%i:%S') AS Hora,  -- <- string “HH:MM:SS”
        Incidencia, TipoSF, Importe
      FROM vMovimientos
      {where_sql}
      ORDER BY Folio, Fecha, Hora
      LIMIT %s OFFSET %s
    """
    sql_count = f"SELECT COUNT(*) FROM vMovimientos {where_sql}"

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # total
    cur.execute(sql_count, tuple(params))
    total = int(cur.fetchone()["COUNT(*)"])

    # datos
    cur.execute(sql_data, tuple(params + [limit, offset]))
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return total, rows