# models/mmv.py
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import time, date

class AbrirBitacoraIn(BaseModel):
    idCentro: str = Field(..., min_length=1, max_length=10)
    hora: Optional[time] = None          # si no llega, se toma NOW()
    anfitrion: int
    idUsuarios: int
    idIncidencia: Optional[int] = None    # no requerido por el SP mmv_abrir_folio
    caja: Optional[int] = 0
    cajero: Optional[int] = 0
    comentario: Optional[str] = None

class AbrirBitacoraOut(BaseModel):
    estatus: int
    mensaje: str
    folio: int
    detalle: int
class RegistrarMovimientoIn(BaseModel):
    idCentro: str = Field(..., min_length=1, max_length=10)
    movimiento: str = Field(..., min_length=1, max_length=1)  # 'R','C','A', etc.
    hora: Optional[time] = None
    caja: Optional[int] = 0
    cajero: Optional[int] = 0
    idIncidencia: int                                     # FK en met_incmanval (obligatorio)
    deposito: str = Field('N', min_length=1, max_length=1) # 'S' | 'N'
    comentario: Optional[str] = None

    # quién registra
    anfitrion: int
    idUsuarios: int

    # SF opcional
    sf: str = Field('N', min_length=1, max_length=1)       # 'S' | 'N'
    tipoSF: str = Field('N', min_length=1, max_length=1)
    sfMonto: Optional[float] = None

class RegistrarMovimientoOut(BaseModel):
    estatus: int
    mensaje: str
    folio: int
    detalle: int

class MovimientoRow(BaseModel):
    Folio: int
    Sucursales: str
    Fecha: date
    Movimiento: str
    Hora: str
    Incidencia: str
    TipoSF: Optional[str] = None
    Importe: Optional[float] = None

class MovimientosOut(BaseModel):
    estatus: int
    total: int
    items: List[MovimientoRow]