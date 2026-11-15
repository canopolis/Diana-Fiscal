"""Cliente de los servicios web de la DGII para e-CF.

Ambientes: TesteCF (pruebas), CerteCF (certificación), eCF (producción).
Flujo: semilla -> firmar semilla -> token (válido ~1 hora) -> enviar / consultar.
"""
import requests
from enum import Enum
from .firma import firmar_xml
from .rfce import es_resumen

URL_ECF = "https://ecf.dgii.gov.do"
URL_FC = "https://fc.dgii.gov.do"


class Ambiente(str, Enum):
    PRUEBAS = "TesteCF"
    CERTIFICACION = "CerteCF"
    PRODUCCION = "eCF"


RUTAS = {
    "semilla": "Autenticacion/api/Autenticacion/Semilla",
    "validar_semilla": "autenticacion/api/Autenticacion/ValidarSemilla",
    "recepcion": "recepcion/api/FacturasElectronicas",
    "recepcion_fc": "recepcionfc/api/recepcion/ecf",
    "consulta_rfce": "consultarfce/api/Consultas/Consulta",
    "aprobacion": "aprobacioncomercial/api/AprobacionComercial",
    "resultado": "consultaresultado/api/Consultas/Estado",
    "estado": "consultaestado/api/Consultas/Estado",
    "trackids": "ConsultaTrackIds/api/TrackIds/Consulta",
    "directorio": "consultadirectorio/api/consultas/obtenerdirectorioporrnc",
    "anulacion": "anulacionrangos/api/operaciones/anularrango",
}

# Emisor <-> receptor (servidores de otros contribuyentes)
RUTAS_RECEPTOR = {
    "semilla": "fe/autenticacion/api/semilla",
    "validar_semilla": "fe/autenticacion/api/validacioncertificado",
    "recepcion": "fe/recepcion/api/ecf",
    "aprobacion": "fe/aprobacioncomercial/api/ecf",
}


class ErrorDGII(Exception):
    def __init__(self, mensaje, estado=None, datos=None):
        super().__init__(mensaje)
        self.estado, self.datos = estado, datos


class ClienteDGII:
    def __init__(self, certificado, ambiente=Ambiente.PRUEBAS, token=None, tiempo=60):
        self.cert = certificado
        self.ambiente = Ambiente(ambiente)
        self.s = requests.Session()
        self.s.headers["Accept"] = "application/json"
        self.tiempo = tiempo
        if token:
            self.s.headers["Authorization"] = f"Bearer {token}"

    def _url(self, clave, base=URL_ECF):
        return f"{base}/{self.ambiente.value}/{RUTAS[clave]}"

    def _r(self, metodo, url, **kw):
        try:
            r = self.s.request(metodo, url, timeout=self.tiempo, **kw)
        except requests.RequestException as e:
            raise ErrorDGII(f"Sin conexión con {url}: {e}")
        if r.status_code >= 400:
            try:
                datos = r.json()
            except ValueError:
                datos = r.text
            raise ErrorDGII(f"DGII respondió {r.status_code} en {url}", r.status_code, datos)
        ct = r.headers.get("Content-Type", "")
        return r.json() if "json" in ct else r.text

    @staticmethod
    def _archivo(xml, nombre):
        return {"xml": (nombre, xml.encode("utf-8") if isinstance(xml, str) else xml, "text/xml")}

    # --- autenticación ---
    def autenticar(self, host_receptor=None):
        if host_receptor:
            base = host_receptor.rstrip("/")
            u_sem, u_val = f"{base}/{RUTAS_RECEPTOR['semilla']}", f"{base}/{RUTAS_RECEPTOR['validar_semilla']}"
        else:
            u_sem, u_val = self._url("semilla"), self._url("validar_semilla")
        semilla = self._r("GET", u_sem, headers={"Accept": "application/xml"})
        if isinstance(semilla, dict):
            raise ErrorDGII("La semilla no llegó como XML", datos=semilla)
        firmada = firmar_xml(semilla, self.cert)
        datos = self._r("POST", u_val, files=self._archivo(firmada, "semilla.xml"))
        token = datos.get("token") if isinstance(datos, dict) else None
        if not token:
            raise ErrorDGII("La DGII no devolvió token", datos=datos)
        if not host_receptor:
            self.s.headers["Authorization"] = f"Bearer {token}"
        return datos   # {"token", "expira", "expedido"}

    # --- envío ---
    def enviar_ecf(self, xml_firmado, nombre):
        """Envía e-CF firmado. Respuesta: {"trackId", "error", "mensaje"}."""
        return self._r("POST", self._url("recepcion"), files=self._archivo(xml_firmado, nombre))

    def enviar_resumen(self, rfce_firmado, nombre):
        """Envía RFCE (E32 < 250,000) a fc.dgii.gov.do. Respuesta con estado y codigo."""
        return self._r("POST", self._url("recepcion_fc", URL_FC), files=self._archivo(rfce_firmado, nombre))

    def enviar_aprobacion(self, acecf_firmado, nombre):
        return self._r("POST", self._url("aprobacion"), files=self._archivo(acecf_firmado, nombre))

    def anular_secuencias(self, anecf_firmado, nombre):
        return self._r("POST", self._url("anulacion"), files=self._archivo(anecf_firmado, nombre))

    def enviar_a_receptor(self, host_receptor, xml_firmado, nombre, token):
        """Envía el e-CF al servidor del cliente (si está en el directorio de receptores)."""
        url = f"{host_receptor.rstrip('/')}/{RUTAS_RECEPTOR['recepcion']}"
        return self._r("POST", url, files=self._archivo(xml_firmado, nombre),
                       headers={"Authorization": f"Bearer {token}"})

    # --- consultas ---
    def resultado(self, track_id):
        """Estado de un envío: Aceptado, Aceptado Condicional, Rechazado, En Proceso."""
        return self._r("GET", self._url("resultado"), params={"trackId": track_id})

    def track_ids(self, rnc_emisor, encf):
        try:
            return self._r("GET", self._url("trackids"), params={"rncEmisor": rnc_emisor, "encf": encf}) or []
        except ErrorDGII as e:
            if e.estado == 400 and "no encontrado" in str(e.datos).lower():
                return []
            raise

    def estado_ecf(self, rnc_emisor, encf, rnc_comprador=None, codigo_seguridad=None):
        p = {"rncEmisor": rnc_emisor, "ncfElectronico": encf}
        if rnc_comprador:
            p["rncComprador"] = rnc_comprador
        if codigo_seguridad:
            p["codigoSeguridad"] = codigo_seguridad
        return self._r("GET", self._url("estado"), params=p)

    def consulta_resumen(self, rnc_emisor, encf, codigo_seguridad):
        """Solo funciona en producción."""
        return self._r("GET", self._url("consulta_rfce", URL_FC),
                       params={"rnc_emisor": rnc_emisor, "encf": encf, "cod_seguridad_eCF": codigo_seguridad})

    def directorio(self, rnc):
        """URLs de recepción de un contribuyente receptor electrónico (lista)."""
        d = self._r("GET", self._url("directorio"), params={"rnc": rnc})
        if d in (None, ""):
            return []
        return d if isinstance(d, list) else [d]

    def ya_recibido(self, rnc_emisor, encf, monto_total=None, codigo_seguridad=None, rnc_comprador=None):
        """Antes de reenviar un documento cuya respuesta se perdió: ¿la DGII ya lo tiene?
        Devuelve "Aceptado", "Aceptado Condicional", "En Proceso", "Rechazado" o "No encontrado"."""
        if monto_total is not None and es_resumen(encf, monto_total):
            r = self.estado_ecf(rnc_emisor, encf, rnc_comprador, codigo_seguridad)
            return {0: "No encontrado", 1: "Aceptado", 2: "Rechazado"}.get(int(r.get("codigo", -1)), str(r))
        lista = self.track_ids(rnc_emisor, encf)
        for prioridad in ("Aceptado", "Aceptado Condicional", "En Proceso", "Rechazado"):
            if any(x.get("estado") == prioridad for x in lista):
                return prioridad
        return "No encontrado"
