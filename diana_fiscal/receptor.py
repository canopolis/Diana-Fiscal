"""Servidor emisor-receptor: para RECIBIR e-CF de suplidores (y aprobaciones comerciales).

La DGII exige que un receptor electrónico tenga una URL pública siempre encendida
(HTTPS) con estas rutas:
  GET  /fe/autenticacion/api/semilla               -> entrega semilla XML
  POST /fe/autenticacion/api/validacioncertificado -> recibe semilla firmada, da token
  POST /fe/recepcion/api/ecf                       -> recibe e-CF, responde ARECF firmado
  POST /fe/aprobacioncomercial/api/ecf             -> recibe ACECF de clientes
Este servidor es básico (http.server). En producción debe ir detrás de HTTPS.
"""
import base64, os, secrets, time
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from lxml import etree
from .firma import firmar_xml, verificar_firma
from .documentos import acuse_recibo
from .util import fecha_hora_dgii

TIPOS_NO_RECIBIBLES = {"32", "41", "43", "45", "46", "47"}


def _xml_del_multipart(cuerpo, content_type):
    msg = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + cuerpo)
    for parte in msg.iter_parts():
        nombre = parte.get_filename() or "documento.xml"
        return nombre, parte.get_payload(decode=True)
    raise ValueError("Sin archivo en el formulario")


def crear_servidor(certificado, rnc_propio, carpeta="recibidos", puerto=8443, host="0.0.0.0"):
    os.makedirs(carpeta, exist_ok=True)
    tokens = {}

    class Manejador(BaseHTTPRequestHandler):
        def _responder(self, codigo, cuerpo, tipo="application/xml"):
            datos = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else cuerpo
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def _leer(self):
            n = int(self.headers.get("Content-Length", 0))
            return _xml_del_multipart(self.rfile.read(n), self.headers.get("Content-Type", ""))

        def _autorizado(self):
            t = self.headers.get("Authorization", "").replace("Bearer ", "")
            return tokens.get(t, 0) > time.time()

        def do_GET(self):
            if self.path.lower().startswith("/fe/autenticacion/api/semilla"):
                v = base64.b64encode(secrets.token_bytes(48)).decode()
                self._responder(200, f'<?xml version="1.0" encoding="utf-8"?><SemillaModel '
                                     f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                                     f'xmlns:xsd="http://www.w3.org/2001/XMLSchema"><valor>{v}</valor>'
                                     f'<fecha>{time.strftime("%Y-%m-%dT%H:%M:%S")}</fecha></SemillaModel>')
            else:
                self._responder(404, "")

        def do_POST(self):
            ruta = self.path.lower()
            try:
                nombre, xml = self._leer()
            except Exception as e:
                return self._responder(400, f"Formulario inválido: {e}", "text/plain")
            if ruta.startswith("/fe/autenticacion/api/validacioncertificado"):
                if not verificar_firma(xml):
                    return self._responder(401, '{"error":"firma inválida"}', "application/json")
                t = secrets.token_urlsafe(32)
                tokens[t] = time.time() + 3600
                return self._responder(200, f'{{"token":"{t}","expira":"{fecha_hora_dgii()}"}}', "application/json")
            if not self._autorizado():
                return self._responder(401, "", "text/plain")
            nombre = os.path.basename(nombre)
            with open(os.path.join(carpeta, nombre), "wb") as f:
                f.write(xml)
            if ruta.startswith("/fe/recepcion/api/ecf"):
                return self._responder(200, self._acuse(xml))
            if ruta.startswith("/fe/aprobacioncomercial/api/ecf"):
                return self._responder(200, "", "text/plain")
            self._responder(404, "")

        def _acuse(self, xml):
            r = etree.fromstring(xml)
            g = lambda t: (r.findtext(f".//{t}") or "").strip()
            emisor, comprador, encf, tipo = g("RNCEmisor"), g("RNCComprador"), g("eNCF"), g("TipoeCF")
            motivo = None
            if tipo in TIPOS_NO_RECIBIBLES:
                motivo = 1
            elif not verificar_firma(xml):
                motivo = 2
            elif comprador != rnc_propio:
                motivo = 4
            return firmar_xml(acuse_recibo(emisor, comprador, encf, motivo is None, motivo), certificado)

        def log_message(self, *a):
            pass

    return ThreadingHTTPServer((host, puerto), Manejador)
