import copy
from lxml import etree
from signxml import XMLVerifier
from diana_fiscal import (firmar_xml, verificar_firma, codigo_seguridad, construir_ecf, ecf32_a_rfce,
                          es_resumen, nombre_archivo, qr, documentos)
from diana_fiscal.ecf import validar_basico
from diana_fiscal.facturador import Facturador
from diana_fiscal.receptor import crear_servidor

SEMILLA = ('<?xml version="1.0" encoding="utf-8"?><SemillaModel xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xmlns:xsd="http://www.w3.org/2001/XMLSchema"><valor>abc==</valor><fecha>2026-11-15T10:00:00</fecha></SemillaModel>')


def _ok_externo(xml, cert):
    from cryptography.hazmat.primitives.serialization import Encoding
    XMLVerifier().verify(xml.encode(), x509_cert=cert.cert.public_bytes(Encoding.PEM).decode(),
                         ignore_ambiguous_key_info=True)


def test_firma_semilla(cert):
    f = firmar_xml(SEMILLA, cert)
    assert verificar_firma(f)
    _ok_externo(f, cert)                    # verificación independiente (signxml)
    assert f.count("<Signature xmlns") == 1 and "\n" not in f


def test_firma_detecta_cambio(cert):
    f = firmar_xml(SEMILLA, cert).replace("abc==", "xyz==")
    assert not verificar_firma(f)


def test_orden_ecf(factura31):
    d = copy.deepcopy(factura31)
    d["Encabezado"] = dict(reversed(list(d["Encabezado"].items())))
    r = etree.fromstring(construir_ecf(d).encode())
    assert [c.tag for c in r] == ["Encabezado", "DetallesItems", "FechaHoraFirma"]
    assert [c.tag for c in r[0]] == ["Version", "IdDoc", "Emisor", "Comprador", "Totales"]


def test_ecf_firmado(cert, factura31):
    assert validar_basico(factura31) == []
    f = firmar_xml(construir_ecf(factura31), cert)
    _ok_externo(f, cert)
    assert len(codigo_seguridad(f)) == 6
    assert nombre_archivo("131234567", "E310000000001") == "131234567E310000000001.xml"


def test_validacion(factura31):
    d = copy.deepcopy(factura31)
    d["Encabezado"]["IdDoc"]["eNCF"] = "E31001"
    d["Encabezado"]["Totales"]["MontoTotal"] = "1"
    assert len(validar_basico(d)) == 2


def test_rfce(cert, factura31):
    d = copy.deepcopy(factura31)
    d["Encabezado"]["IdDoc"].update(TipoeCF=32, eNCF="E320000000001")
    assert es_resumen("E320000000001", 6000) and not es_resumen("E320000000001", 250000)
    f = firmar_xml(construir_ecf(d), cert)
    rfce, cod = ecf32_a_rfce(f)
    r = etree.fromstring(rfce.encode())
    assert r.tag == "RFCE" and r.findtext("Encabezado/CodigoSeguridadeCF") == cod
    assert r.find("Encabezado/IdDoc/FechaVencimientoSecuencia") is None
    _ok_externo(firmar_xml(rfce, cert), cert)


def test_qr():
    u = qr.url_qr_ecf("131234567", "E310000000001", "6000.00", "15-11-2026", "15-11-2026 10:00:00", "AbC123",
                      "101672919", "TesteCF")
    assert u.startswith("https://ecf.dgii.gov.do/testecf/consultatimbre?") and "RncComprador=101672919" in u
    assert "fechafirma=15-11-2026%2010%3A00%3A00" in u
    assert qr.url_qr_consumo("1", "E32", 5, "x").startswith("https://fc.dgii.gov.do/ecf/consultatimbrefc")


def test_documentos(cert):
    a = documentos.anulacion("131234567", [(31, "E310000000010", "E310000000015")])
    assert "<CantidadeNCFAnulados>6</CantidadeNCFAnulados>" in a
    for x in (a, documentos.aprobacion_comercial("1", "E310000000001", "15-11-2026", "6000.00", "2"),
              documentos.acuse_recibo("1", "2", "E310000000001")):
        _ok_externo(firmar_xml(x, cert), cert)


class FalsoAPI:
    def __init__(self): self.enviados = []
    def autenticar(self): return {"token": "t"}
    def enviar_ecf(self, xml, n): self.enviados.append(("ecf", n)); return {"trackId": "T1"}
    def enviar_resumen(self, xml, n): self.enviados.append(("rfce", n)); return {"estado": "Aceptado"}
    def resultado(self, t): return {"estado": "Aceptado", "trackId": t}


def test_facturador(cert, factura31, tmp_path):
    api = FalsoAPI()
    f = Facturador(cert, carpeta=str(tmp_path), cliente=api)
    r = f.emitir(factura31)
    assert r["estado"] == "Aceptado" and r["trackId"] == "T1" and api.enviados == [("ecf", "131234567E310000000001.xml")]
    d = copy.deepcopy(factura31)
    d["Encabezado"]["IdDoc"].update(TipoeCF=32, eNCF="E320000000002")
    r = f.emitir(d)
    assert r["resumen"] and api.enviados[-1][0] == "rfce" and "consultatimbrefc" in r["qr"]


def test_receptor(cert, factura31, tmp_path):
    import threading, requests
    srv = crear_servidor(cert, "101672919", str(tmp_path), puerto=0, host="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    s = requests.Session(); s.trust_env = False
    sem = s.get(base + "/fe/autenticacion/api/semilla").text
    tok = s.post(base + "/fe/autenticacion/api/validacioncertificado",
                 files={"xml": ("s.xml", firmar_xml(sem, cert))}).json()["token"]
    ecf = firmar_xml(construir_ecf(factura31), cert)
    r = s.post(base + "/fe/recepcion/api/ecf", files={"xml": ("x.xml", ecf)},
               headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 200 and "<Estado>0</Estado>" in r.text and verificar_firma(r.text)
    srv.shutdown()
