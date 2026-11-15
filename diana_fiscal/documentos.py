"""Otros documentos firmados: anulación de secuencias, aprobación comercial y acuse de recibo."""
from .ecf import construir_xml
from .util import fecha_hora_dgii

ORDEN_ANECF = {
    "ANECF": ["Encabezado", "DetalleAnulacion"],
    "Encabezado": ["Version", "RncEmisor", "CantidadeNCFAnulados", "FechaHoraAnulacioneNCF"],
    "DetalleAnulacion": ["Anulacion"],
    "Anulacion": ["NoLinea", "TipoeCF", "TablaRangoSecuenciasAnuladaseNCF", "CantidadeNCFAnulados"],
    "TablaRangoSecuenciasAnuladaseNCF": ["Secuencias"],
    "Secuencias": ["SecuenciaeNCFDesde", "SecuenciaeNCFHasta"],
}


def anulacion(rnc_emisor, rangos, fecha_hora=None):
    """Anular secuencias no usadas.
    rangos = [(tipo, "E310000000010", "E310000000015"), ...] (un rango por línea)."""
    lineas, total = [], 0
    for n, (tipo, desde, hasta) in enumerate(rangos, 1):
        cant = int(hasta[3:]) - int(desde[3:]) + 1
        if cant < 1:
            raise ValueError(f"Rango {desde}-{hasta} inválido")
        total += cant
        lineas.append({"NoLinea": n, "TipoeCF": tipo,
                       "TablaRangoSecuenciasAnuladaseNCF": {"Secuencias": {"SecuenciaeNCFDesde": desde,
                                                                         "SecuenciaeNCFHasta": hasta}},
                       "CantidadeNCFAnulados": cant})
    datos = {"Encabezado": {"Version": "1.0", "RncEmisor": rnc_emisor, "CantidadeNCFAnulados": total,
                            "FechaHoraAnulacioneNCF": fecha_hora or fecha_hora_dgii()},
             "DetalleAnulacion": {"Anulacion": lineas}}
    return construir_xml("ANECF", datos, ORDEN_ANECF)


ORDEN_ACECF = {
    "ACECF": ["DetalleAprobacionComercial"],
    "DetalleAprobacionComercial": ["Version", "RNCEmisor", "eNCF", "FechaEmision", "MontoTotal",
                                   "RNCComprador", "Estado", "DetalleMotivoRechazo",
                                   "FechaHoraAprobacionComercial"],
}


def aprobacion_comercial(rnc_emisor, encf, fecha_emision, monto_total, rnc_comprador,
                         aprobado=True, motivo_rechazo="", fecha_hora=None):
    """Aprobación (Estado 1) o rechazo (Estado 2) comercial de un e-CF recibido de un suplidor."""
    d = {"Version": "1.0", "RNCEmisor": rnc_emisor, "eNCF": encf, "FechaEmision": fecha_emision,
         "MontoTotal": monto_total, "RNCComprador": rnc_comprador, "Estado": 1 if aprobado else 2,
         "DetalleMotivoRechazo": None if aprobado else motivo_rechazo,
         "FechaHoraAprobacionComercial": fecha_hora or fecha_hora_dgii()}
    return construir_xml("ACECF", {"DetalleAprobacionComercial": d}, ORDEN_ACECF)


ORDEN_ARECF = {
    "ARECF": ["DetalleAcusedeRecibo"],
    "DetalleAcusedeRecibo": ["Version", "RNCEmisor", "RNCComprador", "eNCF", "Estado",
                             "CodigoMotivoNoRecibido", "FechaHoraAcuseRecibo"],
}

# Estado: 0 = e-CF Recibido, 1 = e-CF No Recibido
# CodigoMotivoNoRecibido: 1 error de especificación, 2 error de firma, 3 envío duplicado, 4 RNC comprador no corresponde


def acuse_recibo(rnc_emisor, rnc_comprador, encf, recibido=True, motivo=None, fecha_hora=None):
    d = {"Version": "1.0", "RNCEmisor": rnc_emisor, "RNCComprador": rnc_comprador, "eNCF": encf,
         "Estado": 0 if recibido else 1, "CodigoMotivoNoRecibido": None if recibido else motivo,
         "FechaHoraAcuseRecibo": fecha_hora or fecha_hora_dgii()}
    return construir_xml("ARECF", {"DetalleAcusedeRecibo": d}, ORDEN_ARECF)
