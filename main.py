# main.py

import uvicorn
from fastapi import FastAPI, Request, Path, APIRouter
from fastapi.responses import JSONResponse
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from DAO import ApcDAO, mermaDAO
from DAO.mermaDAO import get_motivos_merma, get_productos_catalogo, eliminar_producto_detalle, get_productos_merma, \
    get_mermas_by_sucursales, agregar_producto_detalle, crear_merma_cabecera, get_merma_by_id
from models.merma import MotivoMermaResponse, MermaResponse, Merma, MermaCreate
from DAO.ApcDAO import equipos_existen, crear_apci
from DAO.IncidenciasDAO import list_incidencias
from DAO.NivelesDAO import list_niveles
from DAO.StatsDAO import get_dashboard_stats
from DAO.DashboardDAO import (
    get_resumen_merma,
    get_resumen_recuperaciones,
    get_resumen_caducidad,
    get_resumen_manejo_valores,
    get_merma_vs_recuperaciones,
    get_top_productos_merma,
    get_top_productos_recuperacion,
    get_caducidad_por_zona,
    get_merma_por_motivo,
    get_recuperacion_por_tipo,
)
from models.dashboard import (
    DashboardResumenOut, MermaKpi, RecuperacionesKpi, CaducidadKpi, ManejoValoresKpi,
    DashboardGraficasOut, MermaVsRecuperacion, TopProducto,
    CaducidadPorZona, MermaPorMotivo, RecuperacionPorTipo,
)
from DAO.SucursalesDAO import list_sucursales, list_sucursales_no_asignadas
from DAO.ZonasDAO import list_zonas
from DAO.CaducidadDAO import (
    create_cad_registro,
    list_cad_registros,
    get_cad_registro_by_id,
    list_cad_acciones,
    get_cad_cierre,
    create_cad_accion,
    close_cad_registro,
    get_cad_resumen,
)
from DAO.RecuperacionesDAO import (
    list_tipos_recuperacion,
    list_proveedores,
    get_proveedor,
    create_proveedor,
    update_proveedor,
    baja_proveedor,
    asignar_proveedor_zona,
    list_proveedores_por_centro,
    create_recuperacion,
    list_recuperaciones,
    get_recuperacion_by_id,
    get_detalle_recuperacion,
    add_evidencia,
    update_estatus_recuperacion,
    get_stats_recuperaciones,
)
from models.recuperaciones import (
    ProveedorCreateIn, ProveedorUpdateIn, ProveedorZonaIn,
    RecuperacionCreateIn, EvidenciaCreateIn, UpdateEstatusIn,
    TiposOut, TipoRecuperacionOut,
    ProveedoresPageOut, ProveedorOut, ProveedorItemOut,
    RecuperacionesPageOut, RecuperacionOut, RecuperacionDetalleOut,
    DetalleOut, EvidenciaOut, OperacionOut,
    RecuperacionesStatsOut, StatsZona, StatsSucursal,
    StatsProveedor, StatsTipo, StatsProducto, StatsMes,
)
from models.apci import ApcCreatedOut, ApcIn
from models.auth import AuthIn, AuthOut, UsuarioOut
from models.caducidad import (
    CadRegistroCreateIn,
    CadAccionCreateIn,
    CadCierreCreateIn,
    CadOperacionOut,
    CadRegistrosPageOut,
    CadRegistroOut,
    CadAccionOut,
    CadCierreOut,
    CadRegistroDetalleOut,
    CadDetalleResponseOut,
)
from models.incidencias import IncidenciasOut, IncidenciaItemOut
from models.niveles import NivelesOut, NivelItemOut
from models.sucursales import SucursalesOut, SucursalItemOut
from models.usuarios import UsuarioUpdateIn, UsuarioUpdatedOut, UsuarioCreateIn, UsuarioCreatedOut, UsuarioBasic, \
    UsuarioGetOut, NivelInfo, SucursalInfo, AsignarSucursalOut, AsignarSucursalIn, UsuarioBajaOut, UsuariosPageOut, \
    UsuarioListItemOut
from DAO.UsuariosDAO import get_usuario_by_id, is_usuario_en_centro, check_password, nivel_exists, sucursal_exists, \
    insert_usuario, assign_usuario_sucursal, upsert_usuario_sucursal, user_exists, update_usuario, get_usuario_row, \
    get_nivel_info, get_sucursales_de_usuario, insert_usuario_sucursal, usuario_sucursal_exists, set_usuario_baja, \
    get_usuario_estatus, usuario_existe, list_usuarios
from models.zonas import ZonasOut, ZonaItemOut
from security import new_session_id, create_access_token, create_refresh_token
from datetime import datetime, date, timedelta
from models.mmv import AbrirBitacoraIn, AbrirBitacoraOut, RegistrarMovimientoOut, RegistrarMovimientoIn, MovimientosOut
from DAO.ManejoValoresDAO import (
    sucursal_existe, usuario_activo, folio_abierto_hoy, call_sp_insertar_manval, incidencia_existe,
    get_movimientos_generales, call_sp_abrir_folio, call_sp_registrar_movimiento
)
from mysql.connector import Error as MySQLError
from security_basic import require_roles
from typing import Optional, Set
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="API Manejo de Valores")
router = APIRouter(tags=["Estadísticas"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite cualquier origen para desarrollo y Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.exception_handler(Exception)
async def all_exc_handler(req: Request, exc: Exception):
    # Quita esto en producción; es para ver el error real
    return JSONResponse(
        status_code=500,
        content={"estatus": 0, "mensaje": f"Consultar usuario: {type(exc).__name__}: {exc}"}
    )

@app.post("/usuarios/autenticar", response_model=AuthOut, tags=["Usuarios"])
async def autenticar(payload: AuthIn, request: Request, idCentro: Optional[str] = None):
    # 1) Presencia ya la valida Pydantic (idUsuarios>0, pwd no vacío)

    # 2) Existencia de usuario
    user = get_usuario_by_id(payload.idUsuarios)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    # 3) Estatus activo
    if int(user["Estatus"]) != 1:
        raise HTTPException(status_code=401, detail="Usuario inactivo")

    # 4) Contraseña
    if not check_password(payload.pwd, user["Contraseña"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    # 5) Nivel/Rol: ya NO se restringe aquí; el front maneja permisos por nivel.
    nivel = int(user["idNivelUsuario"])

    # 6) Sucursal (si se envía idCentro, validar pertenencia)
    id_centro_usuario = None
    if idCentro:
        if not is_usuario_en_centro(user["IdUsuarios"], idCentro):
            raise HTTPException(status_code=403, detail="Usuario no pertenece al centro indicado")
        id_centro_usuario = idCentro

    # Generar sesión y tokens
    id_sesion = new_session_id()
    now_iso   = datetime.utcnow().isoformat() + "Z"
    subject = {
        "user": user["IdUsuarios"],
        "nivel": nivel,
        "idCentro": id_centro_usuario
    }
    access = create_access_token(subject)
    refresh = create_refresh_token(subject)

    # Metadatos (para auditoría)
    meta = {
        "ip": request.client.host if request.client else None,
        "userAgent": request.headers.get("user-agent"),
        "via": request.headers.get("via")
    }

    usuario_out = UsuarioOut(
        user=user["IdUsuarios"],
        nombre=user["NombreUsuario"],
        idNivelUsuario=nivel,
        estatus=user["Estatus"],
        idCentro=id_centro_usuario
    )

    return AuthOut(
        estatus=1,
        mensaje="Autenticación válida",
        usuario=usuario_out,
        idSesion=id_sesion,
        token=access,
        refreshToken=refresh,
        fechaLogin=now_iso,
        metadatos=meta
    )

@app.exception_handler(HTTPException)
async def custom_http_exc_handler(_, exc: HTTPException):
    # Formato de salida homogéneo con tu ficha
    return JSONResponse(
        status_code=exc.status_code,
        content={"estatus": 0, "mensaje": exc.detail}
    )
@app.post("/usuarios", response_model=UsuarioCreatedOut, tags=["Usuarios"])
async def crear_usuario(
    data: UsuarioCreateIn,
    current=Depends(require_roles())  # ← BasicAuth + roles permitidos
):
    # 1) Presencia ya validada por Pydantic

    # 2) Unicidad: idUsuarios no debe existir
    if get_usuario_by_id(data.idUsuarios):
        raise HTTPException(status_code=409, detail="El idUsuarios ya existe")

    # 3) Nivel existente
    if not nivel_exists(data.idNivelUsuario):
        raise HTTPException(status_code=400, detail="NivelUsuario no existe")

    # 4) Sucursal existente
    if not sucursal_exists(data.idCentro):
        raise HTTPException(status_code=400, detail="idCentro no existe")

    # 5) Normalización simple de nombre (opcional)
    nombre_norm = " ".join(data.NombreUsuario.split())

    # 6) Crear usuario
    try:
        estatus_num = 1 if str(data.estatus) in ('A', '1', 'a') else 0
        fecha_alt = insert_usuario(
            idUsuarios=data.idUsuarios,
            nombre=nombre_norm,
            pwd_plain=data.pwd,
            idNivelUsuario=data.idNivelUsuario,
            estatus=estatus_num
        )
        # 7) Registrar vínculo en UsuarioSuc
        assign_usuario_sucursal(data.idUsuarios, data.idCentro)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {e}")

    # 8) Respuesta
    return UsuarioCreatedOut(
        estatus=1,
        mensaje="Usuario creado",
        usuario={
            "idUsuarios": data.idUsuarios,
            "NombreUsuario": nombre_norm,
            "idNivelUsuario": data.idNivelUsuario,
            "estatus": 'A' if data.estatus in ('A', '1') else 'A',
            "FechaAlta": str(fecha_alt),
            "idCentro": data.idCentro
        }
    )
@app.get(
    "/usuarios",
    response_model=UsuariosPageOut,
    tags=["Usuarios"],
    summary="Listar usuarios (paginado y con filtros)"
)
async def listar_usuarios(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    estatus: Optional[int] = Query(None, description="1=activo, 0=baja"),
    idNivelUsuario: Optional[int] = None,
    q: Optional[str] = Query(None, description="Buscar por id/nombre"),
):
    try:
        rows, total = list_usuarios(
            limit=limit,
            offset=offset,
            estatus=estatus,
            idNivelUsuario=idNivelUsuario,
            q=q
        )
        return UsuariosPageOut(
            estatus=1,
            mensaje="OK",
            total=total,
            limit=limit,
            offset=offset,
            usuarios=[UsuarioListItemOut(**r) for r in rows]
        )
    except Exception as e:
        # loguea e si quieres
        raise HTTPException(status_code=500, detail=f"Error al consultar usuarios: {e}")

@app.put("/usuarios/{idUsuarios}", response_model=UsuarioUpdatedOut, tags=["Usuarios"])
async def editar_usuario(
    idUsuarios: int = Path(..., gt=0),
    cambios: UsuarioUpdateIn = ...,
    current = Depends(require_roles())  # BasicAuth + niveles permitidos
):
    # 1) existencia
    if not user_exists(idUsuarios):
        raise HTTPException(status_code=404, detail="Usuario no existe")

    # 2) validaciones opcionales
    if cambios.idNivelUsuario is not None and not nivel_exists(cambios.idNivelUsuario):
        raise HTTPException(status_code=400, detail="idNivelUsuario no existe")

    if cambios.idCentro is not None and not sucursal_exists(cambios.idCentro):
        raise HTTPException(status_code=400, detail="idCentro no existe")

    # 3) normalizar/limpiar nombre si viene
    nombre_norm = None
    if cambios.NombreUsuario is not None:
        nombre_norm = " ".join(cambios.NombreUsuario.split())

    # 4) actualizar usuarios
    rows = update_usuario(
        user_id=idUsuarios,
        nombre=nombre_norm,
        id_nivel=cambios.idNivelUsuario,
        estatus=cambios.estatus
    )

    # 5) reasignación/alta en UsuarioSuc si se envía idCentro
    inserted = False
    if cambios.idCentro is not None:
        inserted = upsert_usuario_sucursal(idUsuarios, cambios.idCentro)

    if rows == 0 and not inserted:
        # Sin cambios efectivos
        return UsuarioUpdatedOut(
            estatus=1,
            mensaje="Sin cambios",
            usuario={
                "idUsuarios": idUsuarios,
                "NombreUsuario": nombre_norm,
                "idNivelUsuario": cambios.idNivelUsuario,
                "estatus": cambios.estatus,
                "idCentro": cambios.idCentro
            }
        )

    # 6) regresar snapshot actual del usuario
    u = get_usuario_by_id(idUsuarios)  # tu DAO ya retorna Estatus como 1/0 si aplicaste el ajuste
    return UsuarioUpdatedOut(
        estatus=1,
        mensaje="Usuario actualizado",
        usuario={
            "idUsuarios": u["IdUsuarios"],
            "NombreUsuario": u["NombreUsuario"],
            "idNivelUsuario": int(u["idNivelUsuario"]),
            "estatus": int(u["Estatus"]),
            "idCentro": cambios.idCentro  # si no se envió, queda None
        }
    )
@app.get("/usuarios/{idUsuarios}", response_model=UsuarioGetOut, tags=["Usuarios"])
async def consultar_usuario_por_id(
    idUsuarios: int = Path(..., gt=0),
    current = Depends(require_roles())   # coord/super/admin
):
    # 1) Traer usuario
    row = get_usuario_row(idUsuarios)
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 2) Mapear usuario (usa FechaAlta)
    usuario_basic = UsuarioBasic(
        idUsuarios     = int(row.get("IdUsuarios")),
        NombreUsuario  = row.get("NombreUsuario"),
        idNivelUsuario = int(row.get("idNivelUsuario")),
        estatus        = int(row.get("Estatus")),
        FechaAlta      = (str(row.get("FechaAlta")) if row.get("FechaAlta") is not None else None)
    )

    # 3) Traer SIEMPRE nivel
    nivel_info = None
    ni = get_nivel_info(usuario_basic.idNivelUsuario)
    if ni:
        nivel_info = NivelInfo(
            idNivelUsuario = int(ni["IdNivelUsuario"]),
            NivelUsuario   = ni["NivelUsuario"]
        )

    # 4) Traer SIEMPRE sucursales asignadas
    sucs_rows = get_sucursales_de_usuario(idUsuarios)
    sucursales_info = [
        SucursalInfo(idCentro=r["idCentro"], Sucursal=r["Sucursal"])
        for r in sucs_rows
    ]

    return {
        "estatus": 1,
        "mensaje": "OK",
        "usuario": usuario_basic,
        "nivel": nivel_info,             # será None si no existe el nivel (raro)
        "sucursales": sucursales_info    # lista (posiblemente vacía si no tiene asignaciones)
    }

@app.post("/usuarios/{idUsuarios}/sucursales",
          response_model=AsignarSucursalOut,
          tags=["Usuarios"])
async def asignar_sucursal_a_usuario(
    idUsuarios: int = Path(..., gt=0),
    body: AsignarSucursalIn = ...,
    current = Depends(require_roles())   # coord/super/admin
):
    id_centro = body.idCentro.strip()

    # 1) Validaciones
    if not id_centro:
        raise HTTPException(status_code=400, detail="idCentro no debe estar vacío")

    if not user_exists(idUsuarios):
        raise HTTPException(status_code=404, detail="Usuario no existe")

    if not sucursal_exists(id_centro):
        raise HTTPException(status_code=404, detail="Sucursal no existe")

    # (Opcional) permitir solo usuarios activos
    urow = get_usuario_row(idUsuarios)
    if not urow or int(urow["Estatus"]) != 1:
        raise HTTPException(status_code=400, detail="Usuario inactivo; no se puede asignar sucursal")

    # 2) No duplicados
    if usuario_sucursal_exists(idUsuarios, id_centro):
        return AsignarSucursalOut(
            estatus=1,
            mensaje="La asignación ya existía",
            asignacion={"idUsuarios": idUsuarios, "idCentro": id_centro}
        )

    # 3) Insertar
    try:
        ra = insert_usuario_sucursal(idUsuarios, id_centro)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al asignar: {type(e).__name__}: {e}")

    if ra <= 0:
        raise HTTPException(status_code=500, detail="No se pudo crear la asignación")

    # 4) OK
    return AsignarSucursalOut(
        estatus=1,
        mensaje="Sucursal asignada al usuario",
        asignacion={"idUsuarios": idUsuarios, "idCentro": id_centro}
    )

@app.delete("/usuarios/{idUsuarios}", response_model=UsuarioBajaOut, tags=["Usuarios"])
async def baja_logica_usuario(
    idUsuarios: int = Path(..., gt=0),
    current = Depends(require_roles())     # coordinador/super/administrador
):
    # 1) existencia
    if not usuario_existe(idUsuarios):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 2) (opcional) impedir auto-baja
    # si tu require_roles() devuelve current["idUsuarios"], úsalo:
    if str(current.get("idUsuarios")) == str(idUsuarios):
        raise HTTPException(status_code=400, detail="No puedes darte de baja a ti mismo")

    # 3) estatus actual (idempotencia)
    est = get_usuario_estatus(idUsuarios)
    if est is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if est == 0:
        # ya estaba dado de baja
        return UsuarioBajaOut(
            estatus=1,
            mensaje="Usuario ya estaba en baja lógica",
            usuario={"idUsuarios": idUsuarios, "estatus": 0}
        )

    # 4) ejecutar baja lógica
    try:
        rc = set_usuario_baja(idUsuarios)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al dar de baja: {type(e).__name__}: {e}")

    if rc <= 0:
        # no cambió nada (otro proceso pudo bajarlo entre lectura y update)
        return UsuarioBajaOut(
            estatus=1,
            mensaje="Usuario ya estaba en baja lógica",
            usuario={"idUsuarios": idUsuarios, "estatus": 0}
        )

    # 5) OK
    return UsuarioBajaOut(
        estatus=1,
        mensaje="Usuario dado de baja lógicamente",
        usuario={"idUsuarios": idUsuarios, "estatus": 0}
    )

@app.post("/mmv/folios", response_model=AbrirBitacoraOut, tags=["Manejo de Valores"])
async def abrir_bitacora(
    body: AbrirBitacoraIn,
    current = Depends(require_roles())   # APP/Coord/Super/Admin (tú decides)
):
    # 1) Validaciones de presencia y existencia
    id_centro = body.idCentro.strip()
    if not id_centro:
        raise HTTPException(status_code=400, detail="idCentro es requerido")

    if not sucursal_existe(id_centro):
        raise HTTPException(status_code=404, detail="Sucursal no existe")

    if not usuario_activo(body.idUsuarios):
        raise HTTPException(status_code=400, detail="Usuario inactivo o inexistente")

    # 2) ¿ya existe folio abierto HOY? (solo para el mensaje; el SP es idempotente)
    folio_existente = folio_abierto_hoy(id_centro)

    # 3) Llamar al SP mmv_abrir_folio: busca folio de HOY o crea el encabezado
    try:
        folio = call_sp_abrir_folio(
            id_centro   = id_centro,
            anfitrion   = body.anfitrion,
            id_usuarios = body.idUsuarios,
            estado      = 'A'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SP mmv_abrir_folio: {type(e).__name__}: {e}")

    return AbrirBitacoraOut(
        estatus = 1,
        mensaje = "Folio ya estaba abierto" if folio_existente else "Folio creado",
        folio   = folio,
        detalle = 0
    )

@app.post("/mmv/movimientos", response_model=RegistrarMovimientoOut, tags=["Manejo de Valores"])
async def registrar_movimiento(
    body: RegistrarMovimientoIn,
    current = Depends(require_roles())     # APP/Coord/Super/Admin según tu política
):
    # 1) Normalización
    id_centro = body.idCentro.strip()
    mov = body.movimiento.strip().upper()
    deposito = body.deposito.strip().upper() if body.deposito else 'N'
    sf = body.sf.strip().upper() if body.sf else 'N'
    tipo_sf = body.tipoSF.strip().upper() if body.tipoSF else 'N'
    hora_txt = body.hora.isoformat() if body.hora else None
    comentario = body.comentario or "MOVIMIENTO"

    # 2) Validaciones
    if not id_centro:
        raise HTTPException(status_code=400, detail="idCentro es requerido")

    if mov not in ('R','C','A'):   # ajusta los permitidos a tu catálogo
        raise HTTPException(status_code=400, detail="Movimiento inválido (usa 'R','C','A')")

    if not sucursal_existe(id_centro):
        raise HTTPException(status_code=404, detail="Sucursal no existe")

    if not usuario_activo(body.idUsuarios):
        raise HTTPException(status_code=400, detail="Usuario inactivo o inexistente")

    if not incidencia_existe(body.idIncidencia):
        raise HTTPException(status_code=404, detail="Incidencia no existe")

    if deposito not in ('S','N'):
        raise HTTPException(status_code=400, detail="deposito debe ser 'S' o 'N'")

    if sf not in ('S','N'):
        raise HTTPException(status_code=400, detail="sf debe ser 'S' o 'N'")

    # 3) El folio debe estar abierto (Estado='A') para esa sucursal en el día de hoy
    folio = folio_abierto_hoy(id_centro)
    if not folio:
        raise HTTPException(status_code=400, detail="No hay folio abierto hoy para esta sucursal; abra la bitácora primero")

    # 4) Llamar al SP mmv_registrar_mov (valida movimiento/folio/incidencia con SIGNAL)
    try:
        det = call_sp_registrar_movimiento(
            folio          = folio,
            movimiento     = mov,               # 'R'|'C'|'A'
            hora_m         = hora_txt,
            caja           = body.caja or 0,
            cajero         = body.cajero or 0,
            id_incidencia  = body.idIncidencia,
            deposito       = deposito,
            comentario     = comentario,
            sf             = sf,
            tipo_sf        = tipo_sf,
            sf_monto       = body.sfMonto
        )
    except MySQLError as e:
        if e.errno == 1644:  # SIGNAL SQLSTATE '45000' del SP
            raise HTTPException(status_code=400, detail=e.msg)
        raise HTTPException(status_code=500, detail=f"SP mmv_registrar_mov: {type(e).__name__}: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SP mmv_registrar_mov: {type(e).__name__}: {e}")

    # 5) Respuesta
    return RegistrarMovimientoOut(
        estatus = 1,
        mensaje = "Movimiento registrado",
        folio   = folio,
        detalle = det
    )

@app.get("/mmv/movimientos", response_model=MovimientosOut, tags=["Manejo de Valores"])
async def listar_movimientos_generales(
    idCentro: Optional[str] = Query(None, description="Sucursal (idCentro, opcional)"),
    fecha: Optional[date] = Query(None, description="Fecha exacta (YYYY-MM-DD)"),
    folio: Optional[int] = Query(None, ge=1, description="Folio opcional"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current = Depends(require_roles())   # ajusta roles según tu política
):
    total, rows = get_movimientos_generales(
        id_centro=idCentro,
        fecha=fecha,
        folio=folio,
        limit=limit,
        offset=offset
    )
    # FastAPI + Pydantic hará el mapeo dict -> modelo en automático
    return MovimientosOut(estatus=1, total=total, items=rows)

# main.py



# ... tu configuración existente ...

@app.get(
    "/niveles-usuario",
    response_model=NivelesOut,
    tags=["Usuarios"],
    summary="Listar niveles de usuario (para combos)"
)
async def obtener_niveles_usuario():
    try:
        rows = list_niveles()
        return NivelesOut(
            estatus=1,
            mensaje="OK",
            niveles=[NivelItemOut(**r) for r in rows]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar niveles: {e}")



# main.py (fragmentos relevantes)


# Lista general (si la usas)
@app.get(
    "/sucursales",
    response_model=SucursalesOut,
    tags=["Catálogos"],
    summary="Listar todas las sucursales"
)
async def obtener_sucursales(
    current = Depends(require_roles())  # opcional
):
    rows = list_sucursales()
    return SucursalesOut(
        estatus=1,
        mensaje="OK",
        sucursales=[SucursalItemOut(**r) for r in rows]
    )


# Sucursales NO asignadas al usuario, con filtro por zona
@app.get(
    "/usuarios/{idUsuarios}/sucursales-disponibles",
    response_model=SucursalesOut,
    tags=["Usuarios"],
    summary="Sucursales no asignadas al usuario (filtro opcional por zona)"
)
async def sucursales_no_asignadas_usuario(
    idUsuarios: int = Path(..., gt=0, description="Id del usuario (usuarios.IdUsuarios)"),
    q: Optional[str] = Query(None, description="Filtro por nombre o idCentro"),
    idZona: Optional[int] = Query(None, description="Filtra por zonas.idZona"),
    zona: Optional[str] = Query(None, description="Filtra por nombre de zona (zonas.Zona LIKE)"),
    current = Depends(require_roles())
):
    if not usuario_existe(idUsuarios):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    rows = list_sucursales_no_asignadas(
        id_usuarios=idUsuarios,
        q=q,
        id_zona=idZona,
        zona_nombre=zona
    )
    return SucursalesOut(
        estatus=1,
        mensaje="OK",
        sucursales=[SucursalItemOut(**r) for r in rows]
    )

@app.get("/Incidencias", response_model=IncidenciasOut, summary="Listar incidencias")
async def api_list_incidencias(
    q: Optional[str] = Query(None, description="Buscar por nombre"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current = Depends(require_roles())  # JWT obligatorio
):
    rows, total = list_incidencias(q, limit, offset)
    return IncidenciasOut(
        estatus=1, mensaje="OK", total=total,
        incidencias=[IncidenciaItemOut(**r) for r in rows]
    )


@app.get(
    "/zonas",
    response_model=ZonasOut,
    tags=["Catálogos"],
    summary="Listar zonas (idZona, Zona)"
)
async def obtener_zonas(
    q: Optional[str] = Query(None, description="Filtro por nombre de zona (LIKE)"),
    current = Depends(require_roles())  # opcional: quítalo si debe ser público
):
    rows = list_zonas(q=q)
    return ZonasOut(
        estatus=1,
        mensaje="OK",
        zonas=[ZonaItemOut(**r) for r in rows]
    )


@app.get("/apci/consultar", tags=["APCI"])
def consultar_apci(
        sucursal: Optional[str] = Query(None),
        tipo: Optional[str] = Query(None, regex="^(A|C)$"),
        fecha_inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
        fecha_fin: Optional[str] = Query(None, description="YYYY-MM-DD"),
        usuario: Optional[int] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        pagina: int = Query(1, ge=1),
        current=Depends(require_roles())
):
    try:
        print("DEBUG - Endpoint /apci/consultar llamado")
        print(f"DEBUG - Parámetros: sucursal={sucursal}, tipo={tipo}, fecha_inicio={fecha_inicio}")
        print(f"DEBUG - fecha_fin={fecha_fin}, usuario={usuario}, limit={limit}, pagina={pagina}")

        offset = (pagina - 1) * limit

        # Obtener registros
        registros = ApcDAO.apci_list(
            sucursal=sucursal,
            tipo=tipo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            usuario=usuario,
            limit=limit,
            offset=offset
        )

        # Obtener total
        total = ApcDAO.apci_count(
            sucursal=sucursal,
            tipo=tipo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            usuario=usuario
        )

        print(f"DEBUG - Registros obtenidos: {len(registros)}")
        print(f"DEBUG - Total en BD: {total}")

        response = {
            "estatus": 1,
            "mensaje": "Registros obtenidos exitosamente",
            "registros": registros,
            "total": total,
            "pagina": pagina
        }

        print(f"DEBUG - Respuesta enviada: estatus={response['estatus']}, total_registros={len(response['registros'])}")
        return response

    except Exception as e:
        print(f"ERROR EN ENDPOINT: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "estatus": 0,
            "mensaje": f"Error al obtener registros: {str(e)}",
            "registros": [],
            "total": 0,
            "pagina": pagina
        }


@router.get("/stats/dashboard", summary="Estadísticas consolidadas (usuarios, zonas, niveles)")
async def stats_dashboard(
    incluir_inactivos: bool = False,  # si True, no filtra por Estatus=1
    current = Depends(require_roles())  # JWT obligatorio
):
    try:
        data = get_dashboard_stats(activos=not incluir_inactivos)
        return {
            "estatus": 1,
            "data": data
        }
    except Exception as e:
        # logging opcional
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {e}")

# registra el router si aún no lo has hecho
app.include_router(router)

apci_router = APIRouter(prefix="/apci", tags=["Apertura/Cierre"])

@apci_router.post("", response_model=ApcCreatedOut, summary="Registrar Apertura/Cierre con detalle")
async def registrar_apertura_cierre(
    body: ApcIn,
    current = Depends(require_roles())  # exige JWT; ajusta roles si aplica
):
    # Validaciones de dominio
    if body.TipoRecorrido not in ('A', 'C'):
        raise HTTPException(status_code=400, detail="TipoRecorrido inválido (A/C)")

    if not sucursal_existe(body.idCentro):
        raise HTTPException(status_code=400, detail="Sucursal (idCentro) no existe")

    if not usuario_existe(body.idUsuario):
        raise HTTPException(status_code=400, detail="Usuario no existe o inactivo")

    ids_equipo = [d.idEquipo for d in body.detalles]
    ok, faltantes = equipos_existen(ids_equipo)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Equipos inexistentes: {faltantes}")

    # Inserción
    try:
        id_apci, total = crear_apci(
            header=body.model_dump(exclude={"detalles"}),
            detalles=[d.model_dump() for d in body.detalles]
        )
        return ApcCreatedOut(
            estatus=1,
            mensaje="AP/CI registrado",
            idApCi=id_apci,
            totalDetalles=total
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar AP/CI: {e}")

# Registra el router
app.include_router(apci_router)
security = HTTPBasic()
def require_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    # misma lógica que ya usas: valida user/pwd en BD y que estatus == 1
    # return dict del usuario autenticado si todo OK
    ...


# main.py (endpoints actualizados)


# Agregar estos endpoints al final de tu main.py, antes del if __name__ == '__main__':

@app.get("/motivos-merma")
async def get_motivos_merma_endpoint():
    """Obtener catálogo de motivos de merma"""
    try:
        motivos = get_motivos_merma()
        return MotivoMermaResponse(
            estatus=1,
            mensaje="Motivos obtenidos exitosamente",
            motivos=motivos
        )
    except Exception as e:
        return MotivoMermaResponse(
            estatus=0,
            mensaje=f"Error al obtener motivos: {str(e)}",
            motivos=[]
        )


@app.get("/productos/buscar")
async def buscar_productos(q: str = None):
    """Buscar productos en el catálogo"""
    try:
        productos = get_productos_catalogo(q)
        return {
            "estatus": 1,
            "mensaje": "Productos obtenidos exitosamente",
            "productos": productos
        }
    except Exception as e:
        return {
            "estatus": 0,
            "mensaje": f"Error al buscar productos: {str(e)}",
            "productos": []
        }


@app.post("/mermas", response_model=MermaResponse)
async def crear_merma(
        merma: MermaCreate,
        current=Depends(require_roles())
):
    """Crear cabecera de merma en met_mame"""
    try:
        # Usar el idUsuario que viene en merma_data directamente
        id_usuario = merma.idUsuario

        print(f"Creando merma con usuario: {id_usuario}")
        print(f"Datos de merma: {merma}")

        merma_id = crear_merma_cabecera(merma, id_usuario)
        if not merma_id:
            return MermaResponse(
                estatus=0,
                mensaje="Error al crear la merma"
            )

        print(f"Merma creada con ID: {merma_id}")

        # Obtener la merma creada para devolverla
        merma_creada = get_merma_by_id(merma_id)

        if merma_creada:
            print(f"Merma recuperada: {merma_creada}")

            # Crear el objeto Merma manualmente para evitar errores de validación
            merma_obj = {
                "idMaMe": merma_creada["idMaMe"],
                "idCentro": merma_creada["idCentro"],
                "Fecha": merma_creada["Fecha"],
                "idUsuario": merma_creada["idUsuario"],
                "Anfitrion": merma_creada["Anfitrion"],
                "nombreSucursal": merma_creada.get("nombreSucursal"),
                "nombreUsuario": merma_creada.get("nombreUsuario")
            }

            try:
                merma_validada = Merma(**merma_obj)
                return MermaResponse(
                    estatus=1,
                    mensaje="Merma creada exitosamente",
                    merma=merma_validada
                )
            except Exception as validation_error:
                print(f"Error de validación: {validation_error}")
                # Retornar éxito aunque no podamos crear el objeto Merma
                return MermaResponse(
                    estatus=1,
                    mensaje=f"Merma creada exitosamente con ID: {merma_id}",
                    merma=None
                )
        else:
            print("No se pudo recuperar la merma creada")
            # Aún así, retornar éxito porque la merma SÍ se creó
            return MermaResponse(
                estatus=1,
                mensaje=f"Merma creada exitosamente con ID: {merma_id}",
                merma=None
            )

    except Exception as e:
        print(f"Error en crear_merma: {e}")
        import traceback
        traceback.print_exc()
        return MermaResponse(
            estatus=0,
            mensaje=f"Error al crear merma: {str(e)}"
        )


@app.post("/mermas/{merma_id}/productos")
async def agregar_producto_a_merma(
        merma_id: int,
        producto_data: dict,
        current=Depends(require_roles())
):
    """Agregar producto al detalle de merma (met_detmame)"""
    try:
        print(f"Intentando agregar producto a merma ID: {merma_id}")
        print(f"Datos del producto: {producto_data}")

        # Verificar directamente en la base de datos
        from DAO.UsuariosDAO import get_conn
        conn = get_conn()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as count FROM met_mame WHERE idMaMe = %s", (merma_id,))
        count_result = cursor.fetchone()
        cursor.close()
        conn.close()

        print(f"Verificación directa - Count: {count_result}")

        if count_result['count'] == 0:
            return {
                "estatus": 0,
                "mensaje": f"Merma con ID {merma_id} no existe en la base de datos"
            }

        # Validar campos requeridos
        required_fields = ['CodigoBarras', 'idMotMer', 'Cantidad']
        for field in required_fields:
            if field not in producto_data or not producto_data[field]:
                return {
                    "estatus": 0,
                    "mensaje": f"Campo requerido faltante: {field}"
                }

        # Agregar producto al detalle directamente
        success = agregar_producto_detalle(merma_id, producto_data)

        if success:
            return {
                "estatus": 1,
                "mensaje": "Producto agregado exitosamente al detalle"
            }
        else:
            return {
                "estatus": 0,
                "mensaje": "Error al agregar producto al detalle"
            }

    except Exception as e:
        print(f"Error en agregar_producto_a_merma: {e}")
        import traceback
        traceback.print_exc()
        return {
            "estatus": 0,
            "mensaje": f"Error al agregar producto: {str(e)}"
        }


@app.get("/mermas/sucursales/{sucursales_ids}")
async def get_mermas_by_sucursales_endpoint(
        sucursales_ids: str,
        current=Depends(require_roles())
):
    print(f"=== DEBUG ENDPOINT get_mermas_by_sucursales ===")
    print(f"sucursales_ids recibido: {sucursales_ids}")

    try:
        # Convertir string de IDs separados por coma a lista
        ids_list = [id_str.strip() for id_str in sucursales_ids.split(',')]
        print(f"IDs procesados: {ids_list}")

        # Llamar al DAO
        mermas_data = get_mermas_by_sucursales(ids_list)
        print(f"Datos recibidos del DAO: {len(mermas_data)} registros")

        # Convertir a formato esperado por el frontend
        mermas = []
        for merma_data in mermas_data:
            print(f"Procesando merma {merma_data.get('idMaMe', 'N/A')}: {merma_data}")

            merma = Merma(
                idMaMe=merma_data['idMaMe'],
                idCentro=merma_data['idCentro'],
                Fecha=merma_data['Fecha'],
                idUsuario=merma_data['idUsuario'],
                Anfitrion=str(merma_data['Anfitrion']),  # ← CONVERTIR A STRING
                nombreSucursal=merma_data.get('nombreSucursal', 'Sin nombre'),
                nombreUsuario=merma_data.get('nombreUsuario', 'Usuario no encontrado')
            )
            mermas.append(merma)
            print(f"Merma convertida: {merma}")

        print(f"=== RESPUESTA FINAL ===")
        print(f"Total mermas a enviar: {len(mermas)}")

        return {
            "estatus": 1,
            "mensaje": "Mermas obtenidas exitosamente",
            "mermas": mermas,
            "merma": None
        }

    except Exception as e:
        print(f"=== ERROR EN ENDPOINT ===")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "estatus": 0,
            "mensaje": f"Error al obtener mermas: {str(e)}",
            "mermas": [],
            "merma": None
        }
@app.get("/mermas/{merma_id}/productos")
async def obtener_productos_merma(
        merma_id: int,
        current=Depends(require_roles())
):
    """Obtener productos del detalle de una merma"""
    try:
        productos = get_productos_merma(merma_id)
        return {
            "estatus": 1,
            "mensaje": "Productos obtenidos exitosamente",
            "productos": productos
        }
    except Exception as e:
        return {
            "estatus": 0,
            "mensaje": f"Error al obtener productos: {str(e)}",
            "productos": []
        }


@app.delete("/mermas/{merma_id}/productos/{detalle_id}")
async def eliminar_producto_merma(
        merma_id: int,
        detalle_id: int,
        current=Depends(require_roles())
):
    """Eliminar un producto del detalle de merma"""
    try:
        success = eliminar_producto_detalle(merma_id, detalle_id)
        if success:
            return {
                "estatus": 1,
                "mensaje": "Producto eliminado exitosamente"
            }
        else:
            return {
                "estatus": 0,
                "mensaje": "No se pudo eliminar el producto"
            }
    except Exception as e:
        return {
            "estatus": 0,
            "mensaje": f"Error al eliminar producto: {str(e)}"
        }


@app.get(
    "/caducidad/resumen",
    tags=["Próximos a caducar"],
    summary="Conteos para el dashboard de caducidad"
)
async def resumen_caducidad(
    idCentro: Optional[str] = Query(None, description="Filtrar por sucursal"),
    current=Depends(require_roles())
):
    try:
        data = get_cad_resumen(id_centro=idCentro)
        return {"estatus": 1, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener resumen: {e}")


@app.post(
    "/caducidad/registros",
    response_model=CadOperacionOut,
    tags=["Próximos a caducar"],
    summary="Crear caso de producto próximo a caducar"
)
async def crear_caso_caducidad(
    body: CadRegistroCreateIn,
    current=Depends(require_roles())
):
    try:
        nuevo_id = create_cad_registro(body)
        return CadOperacionOut(estatus=1, mensaje="Caso creado", idCad=nuevo_id)
    except ValueError as e:
        msg = str(e)
        status = 404 if "no existe" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear caso: {e}")


@app.get(
    "/caducidad/registros",
    response_model=CadRegistrosPageOut,
    tags=["Próximos a caducar"],
    summary="Listar casos de caducidad"
)
async def listar_casos_caducidad(
    estatus: Optional[str] = Query("A", pattern="^(A|C)$"),
    idCentro: Optional[str] = Query(None, description="Sucursal (idCentro)"),
    q: Optional[str] = Query(None, description="Buscar por código de barras o producto"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current=Depends(require_roles())
):
    try:
        rows, total = list_cad_registros(
            estatus=estatus,
            id_centro=idCentro,
            q=q,
            limit=limit,
            offset=offset,
        )
        items = [
            CadRegistroOut(
                idCad=r["idCad"],
                idCentro=r["idCentro"],
                CodigoBarras=r["CodigoBarras"],
                fechaCaducidad=r["fechaCaducidad"],
                cantidadDetectada=r["cantidadDetectada"],
                FechaRegistro=r["FechaRegistro"],
                idUsuarios=r["idUsuarios"],
                diasAlerta=r["diasAlerta"],
                estatus=r["estatus"],
                nota=r.get("nota"),
                diasRestantes=r.get("diasRestantes"),
            )
            for r in rows
        ]
        return CadRegistrosPageOut(
            estatus=1,
            mensaje="OK",
            total=total,
            limit=limit,
            offset=offset,
            items=items,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar casos: {e}")


@app.get(
    "/caducidad/registros/{idCad}",
    response_model=CadDetalleResponseOut,
    tags=["Próximos a caducar"],
    summary="Consultar detalle de un caso"
)
async def detalle_caso_caducidad(
    idCad: int = Path(..., gt=0),
    current=Depends(require_roles())
):
    try:
        registro = get_cad_registro_by_id(idCad)
        if not registro:
            raise HTTPException(status_code=404, detail="Caso no encontrado")

        acciones = list_cad_acciones(idCad)
        cierre = get_cad_cierre(idCad)

        data = CadRegistroDetalleOut(
            registro=CadRegistroOut(**registro),
            acciones=[CadAccionOut(**a) for a in acciones],
            cierre=CadCierreOut(**cierre) if cierre else None,
        )
        return CadDetalleResponseOut(estatus=1, mensaje="OK", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar detalle: {e}")


@app.post(
    "/caducidad/registros/{idCad}/acciones",
    response_model=CadOperacionOut,
    tags=["Próximos a caducar"],
    summary="Agregar acción a caso de caducidad"
)
async def agregar_accion_caducidad(
    idCad: int = Path(..., gt=0),
    body: CadAccionCreateIn = ...,
    current=Depends(require_roles())
):
    try:
        id_accion = create_cad_accion(idCad, body)
        return CadOperacionOut(estatus=1, mensaje="Acción registrada", idCad=idCad, idAccion=id_accion)
    except ValueError as e:
        msg = str(e)
        status = 404 if "no existe" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar acción: {e}")


@app.post(
    "/caducidad/registros/{idCad}/cierre",
    response_model=CadOperacionOut,
    tags=["Próximos a caducar"],
    summary="Cerrar caso de caducidad"
)
async def cerrar_caso_caducidad(
    idCad: int = Path(..., gt=0),
    body: CadCierreCreateIn = ...,
    current=Depends(require_roles())
):
    try:
        id_cierre = close_cad_registro(idCad, body)
        return CadOperacionOut(estatus=1, mensaje="Caso cerrado", idCad=idCad, idCierre=id_cierre)
    except ValueError as e:
        msg = str(e)
        status = 404 if "no existe" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cerrar caso: {e}")




# ═══════════════════════════════════════════════════════════════
# MÓDULO: RECUPERACIONES
# ═══════════════════════════════════════════════════════════════

# ── Catálogos ────────────────────────────────────────────────────────────────

@app.get("/catalogos/tipos-recuperacion", response_model=TiposOut,
         tags=["Recuperaciones"], summary="Tipos de recuperación (combo)")
async def get_tipos_recuperacion(current=Depends(require_roles())):
    try:
        tipos = list_tipos_recuperacion()
        return TiposOut(estatus=1, mensaje="OK", tipos=[TipoRecuperacionOut(**t) for t in tipos])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ── Proveedores ───────────────────────────────────────────────────────────────
prov_router = APIRouter(prefix="/proveedores", tags=["Recuperaciones - Proveedores"])

# IMPORTANTE: rutas fijas ANTES de /{idProveedor}
@prov_router.get("/disponibles", response_model=ProveedoresPageOut,
                 summary="Proveedores disponibles para una sucursal")
async def proveedores_disponibles(
    idCentro: str = Query(..., description="idCentro de la sucursal"),
    current=Depends(require_roles())
):
    try:
        rows = list_proveedores_por_centro(idCentro)
        return ProveedoresPageOut(estatus=1, mensaje="OK", total=len(rows),
                                  items=[ProveedorOut(**r) for r in rows])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@prov_router.get("", response_model=ProveedoresPageOut, summary="Listar proveedores")
async def listar_proveedores(
    q: Optional[str] = Query(None),
    estatus: Optional[int] = Query(None, ge=0, le=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current=Depends(require_roles())
):
    try:
        rows, total = list_proveedores(q=q, estatus=estatus, limit=limit, offset=offset)
        return ProveedoresPageOut(estatus=1, mensaje="OK", total=total,
                                  items=[ProveedorOut(**r) for r in rows])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@prov_router.post("", response_model=OperacionOut, summary="Crear proveedor")
async def crear_proveedor(body: ProveedorCreateIn, current=Depends(require_roles())):
    try:
        nuevo_id = create_proveedor(body)
        return OperacionOut(estatus=1, mensaje="Proveedor creado", id=nuevo_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@prov_router.get("/{idProveedor}", response_model=ProveedorItemOut, summary="Consultar proveedor")
async def consultar_proveedor(idProveedor: int = Path(..., gt=0), current=Depends(require_roles())):
    row = get_proveedor(idProveedor)
    if not row:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return ProveedorItemOut(estatus=1, mensaje="OK", data=ProveedorOut(**row))


@prov_router.put("/{idProveedor}", response_model=OperacionOut, summary="Actualizar proveedor")
async def actualizar_proveedor(
    idProveedor: int = Path(..., gt=0),
    body: ProveedorUpdateIn = ...,
    current=Depends(require_roles())
):
    if not get_proveedor(idProveedor):
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    update_proveedor(idProveedor, body)
    return OperacionOut(estatus=1, mensaje="Proveedor actualizado", id=idProveedor)


@prov_router.delete("/{idProveedor}", response_model=OperacionOut, summary="Baja lógica proveedor")
async def baja_logica_proveedor(idProveedor: int = Path(..., gt=0), current=Depends(require_roles())):
    if not get_proveedor(idProveedor):
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    baja_proveedor(idProveedor)
    return OperacionOut(estatus=1, mensaje="Proveedor dado de baja", id=idProveedor)


@app.post("/proveedor-zona", response_model=OperacionOut,
          tags=["Recuperaciones - Proveedores"], summary="Asignar proveedor a zona")
async def asignar_zona(body: ProveedorZonaIn, current=Depends(require_roles())):
    try:
        res = asignar_proveedor_zona(body.idProveedor, body.idZona)
        msg = "Asignación ya existía" if res == 0 else "Proveedor asignado a zona"
        return OperacionOut(estatus=1, mensaje=msg, id=res or None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


app.include_router(prov_router)


# ── Recuperaciones ────────────────────────────────────────────────────────────
recup_router = APIRouter(prefix="/recuperaciones", tags=["Recuperaciones"])

# IMPORTANTE: /stats y rutas fijas ANTES de /{idRecuperacion}
@recup_router.get("/stats", response_model=RecuperacionesStatsOut,
                  summary="Dashboard / estadísticas de recuperaciones")
async def stats_recuperaciones(
    idCentro: Optional[str] = Query(None),
    idZona: Optional[int] = Query(None),
    fecha_inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="YYYY-MM-DD"),
    current=Depends(require_roles())
):
    try:
        data = get_stats_recuperaciones(
            id_centro=idCentro, id_zona=idZona,
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )
        return RecuperacionesStatsOut(
            estatus=1,
            totalImporte=data["totalImporte"],
            totalEventos=data["totalEventos"],
            porZona=[StatsZona(**r) for r in data["porZona"]],
            porSucursal=[StatsSucursal(**r) for r in data["porSucursal"]],
            porProveedor=[StatsProveedor(**r) for r in data["porProveedor"]],
            porTipo=[StatsTipo(**r) for r in data["porTipo"]],
            topProductos=[StatsProducto(**r) for r in data["topProductos"]],
            porMes=[StatsMes(**r) for r in data["porMes"]],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener stats: {e}")


@recup_router.get("", response_model=RecuperacionesPageOut,
                  summary="Listar recuperaciones con filtros")
async def listar_recuperaciones(
    idCentro: Optional[str] = Query(None),
    idZona: Optional[int] = Query(None),
    idTipoRecuperacion: Optional[int] = Query(None),
    idProveedor: Optional[int] = Query(None),
    fecha_inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="YYYY-MM-DD"),
    idUsuario: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    pagina: int = Query(1, ge=1),
    current=Depends(require_roles())
):
    try:
        offset = (pagina - 1) * limit
        rows, total = list_recuperaciones(
            id_centro=idCentro, id_zona=idZona, id_tipo=idTipoRecuperacion,
            id_proveedor=idProveedor, fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin, id_usuario=idUsuario,
            limit=limit, offset=offset
        )
        items = [RecuperacionOut(**{k: v for k, v in r.items()}) for r in rows]
        return RecuperacionesPageOut(estatus=1, mensaje="OK", total=total,
                                     limit=limit, pagina=pagina, items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar recuperaciones: {e}")


@recup_router.post("", response_model=OperacionOut,
                   summary="Registrar recuperación con detalle")
async def registrar_recuperacion(body: RecuperacionCreateIn, current=Depends(require_roles())):
    try:
        nuevo_id = create_recuperacion(body)
        return OperacionOut(estatus=1, mensaje="Recuperación registrada", id=nuevo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.exception("Error al registrar recuperación")
        raise HTTPException(status_code=500, detail=f"Error al registrar: {type(e).__name__}: {e}")


@recup_router.get("/{idRecuperacion}", response_model=RecuperacionDetalleOut,
                  summary="Consultar detalle de recuperación")
async def detalle_recuperacion(
    idRecuperacion: int = Path(..., gt=0),
    current=Depends(require_roles())
):
    try:
        row = get_recuperacion_by_id(idRecuperacion)
        if not row:
            raise HTTPException(status_code=404, detail="Recuperación no encontrada")
        detalle = get_detalle_recuperacion(idRecuperacion)
        data = RecuperacionOut(
            **{k: v for k, v in row.items()},
            detalle=[DetalleOut(**d) for d in detalle]
        )
        return RecuperacionDetalleOut(estatus=1, mensaje="OK", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {e}")


@recup_router.post("/{idRecuperacion}/evidencias", response_model=OperacionOut,
                   summary="Agregar evidencia a recuperación")
async def agregar_evidencia(
    idRecuperacion: int = Path(..., gt=0),
    body: EvidenciaCreateIn = ...,
    current=Depends(require_roles())
):
    if not get_recuperacion_by_id(idRecuperacion):
        raise HTTPException(status_code=404, detail="Recuperación no encontrada")
    try:
        nuevo_id = add_evidencia(idRecuperacion, body)
        return OperacionOut(estatus=1, mensaje="Evidencia agregada", id=nuevo_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@recup_router.put("/{idRecuperacion}/estatus", response_model=OperacionOut,
                  summary="Cerrar o cancelar recuperación")
async def actualizar_estatus_recuperacion(
    idRecuperacion: int = Path(..., gt=0),
    body: UpdateEstatusIn = ...,
    current=Depends(require_roles())
):
    if not get_recuperacion_by_id(idRecuperacion):
        raise HTTPException(status_code=404, detail="Recuperación no encontrada")
    update_estatus_recuperacion(idRecuperacion, body.estatus)
    msg = "Recuperación activa" if body.estatus == 1 else "Recuperación cancelada"
    return OperacionOut(estatus=1, mensaje=msg, id=idRecuperacion)


app.include_router(recup_router)


# ── DASHBOARD GENERAL ─────────────────────────────────────────────────────────
dash_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dash_router.get("/resumen", response_model=DashboardResumenOut,
                 summary="KPIs generales: merma, recuperaciones, caducidad y manejo de valores")
async def dashboard_resumen(
    idCentro: Optional[str] = Query(None, description="Filtrar por sucursal"),
    idZona: Optional[int] = Query(None, description="Filtrar por zona"),
    fecha_inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="YYYY-MM-DD"),
    current=Depends(require_roles())
):
    try:
        merma   = get_resumen_merma(idCentro, idZona, fecha_inicio, fecha_fin)
        recup   = get_resumen_recuperaciones(idCentro, idZona, fecha_inicio, fecha_fin)
        cad     = get_resumen_caducidad(idCentro, idZona)
        manval  = get_resumen_manejo_valores(idCentro, idZona, fecha_inicio, fecha_fin)
        return DashboardResumenOut(
            estatus=1,
            mensaje="OK",
            fechaInicio=fecha_inicio,
            fechaFin=fecha_fin,
            merma=MermaKpi(**merma),
            recuperaciones=RecuperacionesKpi(**recup),
            caducidad=CaducidadKpi(**cad),
            manejoValores=ManejoValoresKpi(**manval),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en dashboard resumen: {e}")


@dash_router.get("/graficas", response_model=DashboardGraficasOut,
                 summary="Series de datos para gráficas del dashboard")
async def dashboard_graficas(
    idCentro: Optional[str] = Query(None, description="Filtrar por sucursal"),
    idZona: Optional[int] = Query(None, description="Filtrar por zona"),
    fecha_inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="YYYY-MM-DD"),
    meses: int = Query(6, ge=1, le=24, description="Meses hacia atrás para el comparativo"),
    top: int = Query(10, ge=1, le=50, description="Top N productos"),
    current=Depends(require_roles())
):
    try:
        comparativo  = get_merma_vs_recuperaciones(idCentro, idZona, meses)
        top_merma    = get_top_productos_merma(idCentro, idZona, fecha_inicio, fecha_fin, top)
        top_recup    = get_top_productos_recuperacion(idCentro, idZona, fecha_inicio, fecha_fin, top)
        cad_zona     = get_caducidad_por_zona(idCentro)
        por_motivo   = get_merma_por_motivo(idCentro, idZona, fecha_inicio, fecha_fin)
        por_tipo     = get_recuperacion_por_tipo(idCentro, idZona, fecha_inicio, fecha_fin)
        return DashboardGraficasOut(
            estatus=1,
            mensaje="OK",
            mermaVsRecuperaciones=[MermaVsRecuperacion(**r) for r in comparativo],
            topProductosMerma=[TopProducto(**r) for r in top_merma],
            topProductosRecuperacion=[TopProducto(**r) for r in top_recup],
            caducidadPorZona=[CaducidadPorZona(**r) for r in cad_zona],
            mermaPorMotivo=[MermaPorMotivo(**r) for r in por_motivo],
            recuperacionPorTipo=[RecuperacionPorTipo(**r) for r in por_tipo],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en dashboard gráficas: {e}")


app.include_router(dash_router)


if __name__ == '__main__':
    uvicorn.run('main:app',reload=True, port=8000, host='0.0.0.0')
