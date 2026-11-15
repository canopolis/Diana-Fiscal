"""Flujo completo para emitir un e-CF: armar, firmar, enviar, consultar, QR.

    from diana_fiscal import Certificado, ClienteDGII, Ambiente
    from diana_fiscal.facturador import Facturador
    cert = Certificado.desde_archivo("mi_firma.p12", "clave")
    f = Facturador(cert, Ambiente.PRUEBAS, carpeta="C:/Diana/ecf")
    r = f.emitir(datos_factura)       # dict con encf, estado, trackId, qr, codigo, rutas de XML
"""
import json, os, time
from .ecf import construir_ecf, nombre_archivo, validar_basico
from .firma import firmar_xml, codigo_seguridad
from .rfce import ecf32_a_rfce, es_resumen
from .dgii import ClienteDGII, Ambiente
from . import qr


class Facturador:
    def __init__(self, certificado, ambiente=Ambiente.PRUEBAS, carpeta="ecf", cliente=None):
        self.cert = certificado
        self.ambiente = Ambiente(ambiente)
        self.api = cliente or ClienteDGII(certificado, self.ambiente)
        self.carpeta = carpeta
        self._token_hasta = 0
        os.makedirs(carpeta, exist_ok=True)

    def _token(self):
        if time.time() > self._token_hasta:
            self.api.autenticar()
            self._token_hasta = time.time() + 50 * 60   # el token dura 1 hora; renovar antes

    def _guardar(self, nombre, texto):
        ruta = os.path.join(self.carpeta, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
        return ruta

    def preparar(self, datos):
        """Arma y firma sin enviar. Útil para revisar antes."""
        errores = validar_basico(datos)
        if errores:
            raise ValueError("Factura con errores:\n- " + "\n- ".join(errores))
        enc = datos["Encabezado"]
        rnc, encf = enc["Emisor"]["RNCEmisor"], enc["IdDoc"]["eNCF"]
        firmado = firmar_xml(construir_ecf(datos), self.cert)
        cod = codigo_seguridad(firmado)
        total = enc["Totales"]["MontoTotal"]
        resumen = es_resumen(encf, total)
        if resumen:
            url = qr.url_qr_consumo(rnc, encf, total, cod, self.ambiente.value)
        else:
            from lxml import etree
            fhf = etree.fromstring(firmado.encode()).findtext("FechaHoraFirma")
            url = qr.url_qr_ecf(rnc, encf, total, enc["Emisor"]["FechaEmision"], fhf, cod,
                                enc.get("Comprador", {}).get("RNCComprador", ""), self.ambiente.value)
        return {"rnc": rnc, "encf": encf, "xml_firmado": firmado, "codigo_seguridad": cod,
                "resumen": resumen, "qr": url, "total": total}

    def emitir(self, datos, esperar=True):
        p = self.preparar(datos)
        nombre = nombre_archivo(p["rnc"], p["encf"])
        p["ruta_xml"] = self._guardar(nombre, p["xml_firmado"])
        self._token()
        if p["resumen"]:
            rfce, _ = ecf32_a_rfce(p["xml_firmado"])
            rfce_f = firmar_xml(rfce, self.cert)
            p["ruta_rfce"] = self._guardar("RFCE_" + nombre, rfce_f)
            resp = self.api.enviar_resumen(rfce_f, nombre)
            p["respuesta"] = resp
            p["estado"] = resp.get("estado") if isinstance(resp, dict) else str(resp)
        else:
            resp = self.api.enviar_ecf(p["xml_firmado"], nombre)
            p["respuesta"] = resp
            p["trackId"] = resp.get("trackId") if isinstance(resp, dict) else None
            p["estado"] = "En Proceso"
            if esperar and p["trackId"]:
                p.update(self.esperar_resultado(p["trackId"]))
        self._guardar(nombre.replace(".xml", "_resultado.json"),
                      json.dumps({k: v for k, v in p.items() if k != "xml_firmado"}, ensure_ascii=False, indent=2,
                                 default=str))
        return p

    def esperar_resultado(self, track_id, intentos=10, pausa=3):
        r = {}
        for _ in range(intentos):
            r = self.api.resultado(track_id)
            if isinstance(r, dict) and r.get("estado") not in (None, "En Proceso"):
                break
            time.sleep(pausa)
        return {"estado": r.get("estado") if isinstance(r, dict) else str(r), "resultado": r}
