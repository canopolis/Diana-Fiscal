"""Armado del XML e-CF a partir de un diccionario.

El diccionario puede venir en cualquier orden: aquí se ordena según el formato DGII.
Las listas (Item, FormaDePago, CodigosItem, TelefonoEmisor...) se repiten como
elementos hermanos. Valores None o "" se omiten.
"""
from lxml import etree
from .orden_ecf import ORDEN
from .util import fecha_hora_dgii

XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD = "http://www.w3.org/2001/XMLSchema"

# Tipos de e-CF
TIPOS = {
    31: "Factura de Crédito Fiscal Electrónica",
    32: "Factura de Consumo Electrónica",
    33: "Nota de Débito Electrónica",
    34: "Nota de Crédito Electrónica",
    41: "Compras Electrónico",
    43: "Gastos Menores Electrónico",
    44: "Regímenes Especiales Electrónico",
    45: "Gubernamental Electrónico",
    46: "Exportaciones Electrónico",
    47: "Pagos al Exterior Electrónico",
}


def _vacio(v):
    return v is None or v == "" or v == [] or v == {}


def _texto(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def _agregar(padre, tag, valor, orden=ORDEN):
    if _vacio(valor):
        return
    if isinstance(valor, list):
        for v in valor:
            _agregar(padre, tag, v, orden)
        return
    el = etree.SubElement(padre, tag)
    if isinstance(valor, dict):
        _llenar(el, tag, valor, orden)
    else:
        el.text = _texto(valor)


def _llenar(el, tag, datos, orden=ORDEN):
    claves = list(datos)
    conocidas = orden.get(tag, [])
    secuencia = [k for k in conocidas if k in datos] + [k for k in claves if k not in conocidas]
    for k in secuencia:
        _agregar(el, k, datos[k], orden)


def construir_xml(raiz, datos, orden=ORDEN, ns_xsi=True):
    nsmap = {"xsi": XSI, "xsd": XSD} if ns_xsi else None
    el = etree.Element(raiz, nsmap=nsmap)
    _llenar(el, raiz, datos, orden)
    return '<?xml version="1.0" encoding="utf-8"?>' + etree.tostring(el, encoding="unicode")


def construir_ecf(datos, fecha_hora_firma=None):
    """datos = {"Encabezado": {...}, "DetallesItems": {"Item": [...]}, ...}
    Agrega FechaHoraFirma (ahora, hora RD) si no viene. Devuelve XML sin firmar."""
    d = dict(datos.get("ECF", datos))
    d.setdefault("FechaHoraFirma", fecha_hora_firma or fecha_hora_dgii())
    d["Encabezado"].setdefault("Version", "1.0")
    return construir_xml("ECF", d)


def nombre_archivo(rnc_emisor, encf):
    """RNC + e-NCF + .xml, ej. 101672919E310000000001.xml"""
    return f"{rnc_emisor}{encf}.xml"


def validar_basico(datos):
    """Revisión rápida antes de enviar (no sustituye el XSD de la DGII). Lista de errores."""
    e = []
    enc = datos.get("Encabezado", {})
    idd, emi, tot = enc.get("IdDoc", {}), enc.get("Emisor", {}), enc.get("Totales", {})
    encf = str(idd.get("eNCF", ""))
    tipo = str(idd.get("TipoeCF", ""))
    if not (len(encf) == 13 and encf.startswith("E") and encf[1:3] == tipo and encf[3:].isdigit()):
        e.append(f"eNCF '{encf}' no tiene el formato E{tipo}+10 dígitos")
    rnc = str(emi.get("RNCEmisor", ""))
    if not (rnc.isdigit() and len(rnc) in (9, 11)):
        e.append("RNCEmisor debe tener 9 u 11 dígitos")
    if tipo in ("31", "44", "45"):
        if not enc.get("Comprador", {}).get("RNCComprador"):
            e.append(f"El tipo {tipo} requiere RNCComprador")
    if tipo in ("33", "34") and not datos.get("InformacionReferencia"):
        e.append("Las notas de débito/crédito requieren InformacionReferencia (NCF modificado)")
    items = datos.get("DetallesItems", {}).get("Item", [])
    if not items:
        e.append("No hay líneas (DetallesItems/Item)")
    try:
        suma = round(sum(float(i.get("MontoItem", 0)) for i in items), 2)
        exento = float(tot.get("MontoExento", 0) or 0)
        gravado = float(tot.get("MontoGravadoTotal", 0) or 0)
        itbis = float(tot.get("TotalITBIS", 0) or 0)
        total = float(tot.get("MontoTotal", 0))
        if abs(suma - (exento + gravado)) > 0.011:
            e.append(f"Suma de líneas {suma} ≠ exento+gravado {exento + gravado}")
        if abs(total - (exento + gravado + itbis + float(tot.get('MontoImpuestoAdicional', 0) or 0))) > 0.011:
            e.append("MontoTotal no cuadra con exento+gravado+ITBIS")
    except (TypeError, ValueError):
        e.append("Montos no numéricos")
    return e
