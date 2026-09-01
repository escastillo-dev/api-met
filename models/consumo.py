from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class ProdConsumidoCreateIn(BaseModel):
    idCentro: str = Field(..., min_length=1, max_length=4)
    idColaborador: int = Field(..., gt=0, description="Número de nómina del colaborador (sin relación a otra tabla)")
    CodigoBarras: str = Field(..., min_length=1, max_length=20)
    Cantidad: Decimal = Field(1, gt=0)
    idUsuario: int = Field(..., gt=0)
    Comentario: Optional[str] = Field(None, max_length=200)


class ProdConsumidoOut(BaseModel):
    idProdConsumido: int
    Folio: Optional[str] = None
    idCentro: str
    idColaborador: int
    CodigoBarras: str
    Cantidad: Decimal
    idUsuario: int
    FechaRegistro: datetime
    Comentario: Optional[str] = None
    nombreProducto: Optional[str] = None
    nombreSucursal: Optional[str] = None


class ProdConsumidoOperacionOut(BaseModel):
    estatus: int
    mensaje: str
    idProdConsumido: Optional[int] = None
    Folio: Optional[str] = None


class ProdConsumidosPageOut(BaseModel):
    estatus: int
    mensaje: str
    total: int
    limit: int
    offset: int
    items: List[ProdConsumidoOut]


class ProdConsumidoDetalleResponseOut(BaseModel):
    estatus: int
    mensaje: str
    data: Optional[ProdConsumidoOut] = None
