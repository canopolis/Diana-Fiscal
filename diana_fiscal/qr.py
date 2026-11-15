"""Enlaces del código QR que va impreso en la representación impresa del e-CF."""
from urllib.parse import quote


def url_qr_ecf(rnc_emisor, encf, monto_total, fecha_emision, fecha_firma, codigo_seguridad,
               rnc_comprador="", ambiente="eCF"):
    """e-CF normal (y E32 >= 250,000). fecha_emision dd-MM-yyyy, fecha_firma dd-MM-yyyy HH:mm:ss."""
    comprador = ""
    if rnc_comprador and not str(encf).upper().startswith(("E43", "E47")):
        comprador = f"RncComprador={quote(str(rnc_comprador))}&"
    return (f"https://ecf.dgii.gov.do/{ambiente.lower()}/consultatimbre?rncemisor={quote(str(rnc_emisor))}&"
            f"{comprador}encf={quote(str(encf))}&fechaemision={quote(fecha_emision)}&"
            f"montototal={quote(str(monto_total))}&fechafirma={quote(fecha_firma)}&"
            f"codigoseguridad={quote(codigo_seguridad)}")


def url_qr_consumo(rnc_emisor, encf, monto_total, codigo_seguridad, ambiente="eCF"):
    """Factura de consumo E32 menor de RD$250,000."""
    return (f"https://fc.dgii.gov.do/{ambiente.lower()}/consultatimbrefc?rncemisor={quote(str(rnc_emisor))}&"
            f"encf={quote(str(encf))}&montototal={quote(str(monto_total))}&"
            f"codigoseguridad={quote(codigo_seguridad)}")


def imagen_qr(url, ruta_png):
    """Guarda el QR como PNG (requiere el paquete qrcode)."""
    import qrcode
    qrcode.make(url).save(ruta_png)
    return ruta_png
