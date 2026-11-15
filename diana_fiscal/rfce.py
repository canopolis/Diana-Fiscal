"""Resumen de Factura de Consumo Electrónica (RFCE): E32 menor de RD$250,000.

Para esas facturas solo se envía el resumen a fc.dgii.gov.do; el e-CF completo
se firma y se guarda (y se entrega al cliente) pero no se envía.
"""
from lxml import etree
from .ecf import construir_xml
from .firma import codigo_seguridad

LIMITE_RESUMEN = 250000

ORDEN_RFCE = {
    "RFCE": ["Encabezado"],
    "Encabezado": ["Version", "IdDoc", "Emisor", "Comprador", "Totales", "CodigoSeguridadeCF"],
    "IdDoc": ["TipoeCF", "eNCF", "TipoIngresos", "TipoPago", "TablaFormasPago"],
    "TablaFormasPago": ["FormaDePago"],
    "FormaDePago": ["FormaPago", "MontoPago"],
    "Emisor": ["RNCEmisor", "RazonSocialEmisor", "FechaEmision"],
    "Comprador": ["RNCComprador", "IdentificadorExtranjero", "RazonSocialComprador"],
    "Totales": ["MontoGravadoTotal", "MontoGravadoI1", "MontoGravadoI2", "MontoGravadoI3", "MontoExento",
                "TotalITBIS", "TotalITBIS1", "TotalITBIS2", "TotalITBIS3", "MontoImpuestoAdicional",
                "ImpuestosAdicionales", "MontoTotal", "MontoNoFacturable", "MontoPeriodo"],
    "ImpuestosAdicionales": ["ImpuestoAdicional"],
    "ImpuestoAdicional": ["TipoImpuesto", "MontoImpuestoSelectivoConsumoEspecifico",
                          "MontoImpuestoSelectivoConsumoAdvalorem", "OtrosImpuestosAdicionales"],
}


def es_resumen(encf, monto_total):
    try:
        return str(encf).upper().startswith("E32") and float(monto_total) < LIMITE_RESUMEN
    except (TypeError, ValueError):
        return False


def _a_dict(el):
    hijos = list(el)
    if not hijos:
        return el.text
    d = {}
    for h in hijos:
        if not isinstance(h.tag, str):
            continue
        tag = etree.QName(h).localname
        if tag == "Signature":
            continue
        v = _a_dict(h)
        if tag in d:
            if not isinstance(d[tag], list):
                d[tag] = [d[tag]]
            d[tag].append(v)
        else:
            d[tag] = v
    return d


def _filtrar(d, tag):
    campos = ORDEN_RFCE.get(tag)
    if not isinstance(d, dict) or campos is None:
        return d
    out = {}
    for k in campos:
        if k in d:
            v = d[k]
            out[k] = [_filtrar(x, k) for x in v] if isinstance(v, list) else _filtrar(v, k)
    return out


def ecf32_a_rfce(ecf32_firmado):
    """Devuelve (xml_rfce_sin_firmar, codigo_seguridad)."""
    raiz = etree.fromstring(ecf32_firmado.encode() if isinstance(ecf32_firmado, str) else ecf32_firmado)
    datos = _a_dict(raiz)
    cod = codigo_seguridad(ecf32_firmado)
    enc = _filtrar(datos["Encabezado"], "Encabezado")
    enc["CodigoSeguridadeCF"] = cod
    return construir_xml("RFCE", {"Encabezado": enc}, ORDEN_RFCE), cod
