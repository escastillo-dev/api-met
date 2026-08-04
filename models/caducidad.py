from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CadRegistroCreateIn(BaseModel):
    idCentro: str = Field(..., min_length=1, max_length=10)
    CodigoBarras: str = Field(..., min_length=1, max_length=20)
    fechaCaducidad: date
    cantidadDetectada: Decimal = Field(..., gt=0)
    idUsuarios: int = Field(..., gt=0)
    diasAlerta: int = Field(30, ge=1, le=365)
    nota: Optional[str] = Field(None, max_length=200)


class CadAccionCreateIn(BaseModel):
    idTipoAccion: int = Field(..., gt=0)
    cantidad: Optional[Decimal] = Field(None, ge=0)
    resultado: str = Field(..., min_length=2, max_length=45)
    comentario: Optional[str] = Field(None, max_length=200)
    idUsuarios: Optional[int] = Field(None, gt=0)
    idUsuario: Optional[int] = Field(None, gt=0)

    @property
    def id_usuario_resuelto(self) -> int:
        val = self.idUsuarios or self.idUsuario
        if not val:
            raise ValueError("Se requiere idUsuarios")
        return val


class CadCierreCreateIn(BaseModel):
    resultadoFinal: str = Field(..., min_length=2, max_length=45)
    cantidadSalida: Optional[Decimal] = Field(None, ge=0)
    cantidadMerma: Optional[Decimal] = Field(None, ge=0)
    comentario: Optional[str] = Field(None, max_length=200)
    idUsuarios: int = Field(..., gt=0)


class CadRegistroOut(BaseModel):
    idCad: int
    idCentro: str
    CodigoBarras: str
    fechaCaducidad: date
    cantidadDetectada: Decimal
    FechaRegistro: datetime
    idUsuarios: int
    diasAlerta: int
    estatus: str
    nota: Optional[str] = None
    diasRestantes: Optional[int] = None


class CadAccionOut(BaseModel):
    idAccion: int
    idCad: int
    fechaHora: Optional[datetime] = None
    idTipoAccion: int
    cantidad: Optional[Decimal] = None
    resultado: Optional[str] = None
    comentario: Optional[str] = None
    idUsuarios: int


class CadCierreOut(BaseModel):
    idCierre: int
    idCad: int
    fechaCierre: datetime
    resultadoFinal: str
    cantidadSalida: Optional[Decimal] = None
    cantidadMerma: Optional[Decimal] = None
    comentario: Optional[str] = None
    idUsuarios: int


class CadRegistroDetalleOut(BaseModel):
    registro: CadRegistroOut
    acciones: List[CadAccionOut]
    cierre: Optional[CadCierreOut] = None


class CadRegistrosPageOut(BaseModel):
    estatus: int
    mensaje: str
    total: int
    limit: int
    offset: int
    items: List[CadRegistroOut]


class CadOperacionOut(BaseModel):
    estatus: int
    mensaje: str
    idCad: Optional[int] = None
    idAccion: Optional[int] = None
    idCierre: Optional[int] = None


class CadDetalleResponseOut(BaseModel):
    estatus: int
    mensaje: str
    data: Optional[CadRegistroDetalleOut] = None
