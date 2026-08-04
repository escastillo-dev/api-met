from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


# ── MERMA ────────────────────────────────────────────────────────────────────

class MermaKpi(BaseModel):
    totalEventos: int
    totalImporte: Decimal


# ── RECUPERACIONES ────────────────────────────────────────────────────────────

class RecuperacionesKpi(BaseModel):
    totalEventos: int
    totalImporte: Decimal


# ── CADUCIDAD ─────────────────────────────────────────────────────────────────

class CaducidadKpi(BaseModel):
    criticos: int   # ≤ 7 días
    urgentes: int   # 8-15 días
    proximos: int   # 16-30 días
    cerrados: int


# ── MANEJO DE VALORES ─────────────────────────────────────────────────────────

class ManejoValoresKpi(BaseModel):
    foliosAbiertos: int
    foliosCerrados: int
    totalMovimientos: int


# ── RESPUESTA RESUMEN ─────────────────────────────────────────────────────────

class DashboardResumenOut(BaseModel):
    estatus: int
    mensaje: str
    fechaInicio: Optional[str] = None
    fechaFin: Optional[str] = None
    merma: MermaKpi
    recuperaciones: RecuperacionesKpi
    caducidad: CaducidadKpi
    manejoValores: ManejoValoresKpi


# ── GRAFICAS ──────────────────────────────────────────────────────────────────

class MermaVsRecuperacion(BaseModel):
    mes: str
    merma: Decimal
    recuperaciones: Decimal


class TopProducto(BaseModel):
    CodigoBarras: Optional[str] = None
    Producto: Optional[str] = None
    totalCantidad: Decimal
    importe: Decimal


class CaducidadPorZona(BaseModel):
    idZona: Optional[int] = None
    Zona: Optional[str] = None
    criticos: int
    urgentes: int
    proximos: int


class MermaPorMotivo(BaseModel):
    idMotMer: Optional[int] = None
    Motivo: Optional[str] = None
    totalEventos: int
    importe: Decimal


class RecuperacionPorTipo(BaseModel):
    idTipoRecuperacion: Optional[int] = None
    Tipo: Optional[str] = None
    totalEventos: int
    importe: Decimal


class DashboardGraficasOut(BaseModel):
    estatus: int
    mensaje: str
    mermaVsRecuperaciones: List[MermaVsRecuperacion]
    topProductosMerma: List[TopProducto]
    topProductosRecuperacion: List[TopProducto]
    caducidadPorZona: List[CaducidadPorZona]
    mermaPorMotivo: List[MermaPorMotivo]
    recuperacionPorTipo: List[RecuperacionPorTipo]
