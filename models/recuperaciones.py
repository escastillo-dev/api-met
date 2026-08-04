from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ── INPUT MODELS ────────────────────────────────────────────────────────────

class ProveedorCreateIn(BaseModel):
    proveedor: str = Field(..., min_length=2, max_length=100)


class ProveedorUpdateIn(BaseModel):
    proveedor: Optional[str] = Field(None, min_length=2, max_length=100)
    estatus: Optional[int] = Field(None, ge=0, le=1)


class ProveedorZonaIn(BaseModel):
    idProveedor: int = Field(..., gt=0)
    idZona: int = Field(..., gt=0)


class DetalleRecuperacionIn(BaseModel):
    CodigoBarras: str = Field(..., min_length=1, max_length=20)
    cantidad: Decimal = Field(..., gt=0)


class RecuperacionCreateIn(BaseModel):
    idCentro: str = Field(..., min_length=1, max_length=10)
    idTipoRecuperacion: int = Field(..., gt=0)
    idProveedor: Optional[int] = Field(None, gt=0)
    nombreInfractor: Optional[str] = Field(None, max_length=100)
    comentario: Optional[str] = Field(None, max_length=255)
    idUsuario: int = Field(..., gt=0)
    productos: List[DetalleRecuperacionIn] = Field(..., min_length=1)

    @model_validator(mode='after')
    def validar_tipo_proveedor(self):
        # idTipoRecuperacion == 1 → Proveedor → idProveedor obligatorio
        if self.idTipoRecuperacion == 1 and not self.idProveedor:
            raise ValueError("Si el tipo es Proveedor (1), idProveedor es obligatorio")
        if self.idTipoRecuperacion != 1 and not self.nombreInfractor:
            raise ValueError("Si el tipo no es Proveedor, nombreInfractor es obligatorio")
        return self


class EvidenciaCreateIn(BaseModel):
    rutaArchivo: str = Field(..., min_length=1, max_length=255)
    tipoArchivo: Optional[str] = Field(None, max_length=45)
    idUsuario: int = Field(..., gt=0)


class UpdateEstatusIn(BaseModel):
    estatus: int = Field(..., ge=0, le=1)


# ── OUTPUT MODELS ────────────────────────────────────────────────────────────

class TipoRecuperacionOut(BaseModel):
    idTipoRecuperacion: int
    Tipo: str


class ProveedorOut(BaseModel):
    idProveedor: int
    proveedor: str
    estatus: int


class DetalleOut(BaseModel):
    idDetalle: int
    CodigoBarras: str
    Producto: Optional[str] = None
    cantidad: Decimal
    precio: Optional[Decimal] = None
    importe: Optional[Decimal] = None


class RecuperacionOut(BaseModel):
    idRecuperacion: int
    idCentro: str
    Sucursal: Optional[str] = None
    idZona: Optional[int] = None
    Zona: Optional[str] = None
    idTipoRecuperacion: int
    Tipo: Optional[str] = None
    idProveedor: Optional[int] = None
    proveedor: Optional[str] = None
    nombreInfractor: Optional[str] = None
    comentario: Optional[str] = None
    idUsuario: int
    NombreUsuario: Optional[str] = None
    fechaHora: Optional[datetime] = None
    estatus: int
    totalProductos: Optional[int] = None
    importeTotal: Optional[Decimal] = None
    detalle: Optional[List[DetalleOut]] = None


class EvidenciaOut(BaseModel):
    idEvidencia: int
    idRecuperacion: int
    rutaArchivo: str
    tipoArchivo: Optional[str] = None
    fechaRegistro: Optional[datetime] = None
    idUsuario: int


class TiposOut(BaseModel):
    estatus: int
    mensaje: str
    tipos: List[TipoRecuperacionOut]


class ProveedoresPageOut(BaseModel):
    estatus: int
    mensaje: str
    total: int
    items: List[ProveedorOut]


class ProveedorItemOut(BaseModel):
    estatus: int
    mensaje: str
    data: Optional[ProveedorOut] = None


class RecuperacionesPageOut(BaseModel):
    estatus: int
    mensaje: str
    total: int
    limit: int
    pagina: int
    items: List[RecuperacionOut]


class RecuperacionDetalleOut(BaseModel):
    estatus: int
    mensaje: str
    data: Optional[RecuperacionOut] = None


class OperacionOut(BaseModel):
    estatus: int
    mensaje: str
    id: Optional[int] = None


# ── STATS MODELS ─────────────────────────────────────────────────────────────

class StatsZona(BaseModel):
    idZona: Optional[int] = None
    Zona: Optional[str] = None
    total: int
    importe: Decimal


class StatsSucursal(BaseModel):
    idCentro: str
    Sucursal: Optional[str] = None
    total: int
    importe: Decimal


class StatsProveedor(BaseModel):
    idProveedor: Optional[int] = None
    proveedor: Optional[str] = None
    total: int
    importe: Decimal


class StatsTipo(BaseModel):
    idTipoRecuperacion: int
    Tipo: Optional[str] = None
    total: int
    importe: Decimal


class StatsProducto(BaseModel):
    CodigoBarras: Optional[str] = None
    Producto: Optional[str] = None
    totalCantidad: Decimal
    importe: Decimal


class StatsMes(BaseModel):
    mes: str
    total: int


class RecuperacionesStatsOut(BaseModel):
    estatus: int
    totalImporte: Decimal
    totalEventos: int
    porZona: List[StatsZona]
    porSucursal: List[StatsSucursal]
    porProveedor: List[StatsProveedor]
    porTipo: List[StatsTipo]
    topProductos: List[StatsProducto]
    porMes: List[StatsMes]
