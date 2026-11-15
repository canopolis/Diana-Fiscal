from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

ZONA_RD = timezone(timedelta(hours=-4))   # República Dominicana, sin horario de verano


def ahora_rd():
    return datetime.now(ZONA_RD)


def fecha_hora_dgii(dt=None):
    """dd-MM-yyyy HH:mm:ss (FechaHoraFirma, FechaHoraAnulacion, etc.)."""
    return (dt or ahora_rd()).strftime("%d-%m-%Y %H:%M:%S")


def fecha_dgii(d=None):
    """dd-MM-yyyy (FechaEmision, FechaVencimientoSecuencia)."""
    return (d or ahora_rd()).strftime("%d-%m-%Y")


def monto(v, dec=2):
    """Monto con 2 decimales y punto, sin separador de miles."""
    q = Decimal(1).scaleb(-dec)
    return str(Decimal(str(v)).quantize(q, rounding=ROUND_HALF_UP))
