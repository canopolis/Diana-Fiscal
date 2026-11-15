"""Firma XMLDSig "enveloped" como la exige la DGII.

- Canonicalización C14N 1.0 (http://www.w3.org/TR/2001/REC-xml-c14n-20010315)
- Firma RSA-SHA256, digest SHA-256, Reference URI="" con transform enveloped-signature
- La firma va como último hijo del elemento raíz
- El XML se limpia de espacios entre etiquetas y comentarios antes de firmar
  (si no, el digest de la DGII no coincide).
"""
import base64, hashlib
from lxml import etree
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


def _limpiar(nodo):
    for hijo in list(nodo):
        if not isinstance(hijo.tag, str):          # comentarios, PI
            nodo.remove(hijo)
            continue
        _limpiar(hijo)
    if len(nodo):
        if nodo.text is not None and not nodo.text.strip():
            nodo.text = None
        for hijo in nodo:
            if hijo.tail is not None and not hijo.tail.strip():
                hijo.tail = None


def _c14n(elem):
    """C14N inclusiva. Para un subelemento se hace sobre una copia que conserva los
    namespaces heredados (libxml2 falla canonicalizando subárboles directamente)."""
    import copy
    if elem.getparent() is not None:
        nuevo = etree.Element(elem.tag, attrib=dict(elem.attrib), nsmap=elem.nsmap)
        nuevo.text = elem.text
        for h in elem:
            nuevo.append(copy.deepcopy(h))
        elem = nuevo
    return etree.tostring(etree.ElementTree(elem), method="c14n", exclusive=False, with_comments=False)


def _parsear(xml):
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    parser = etree.XMLParser(remove_blank_text=True, remove_comments=True, resolve_entities=False, no_network=True)
    return etree.fromstring(xml, parser)


def firmar_xml(xml, certificado):
    """Devuelve el XML firmado (str, con declaración utf-8)."""
    raiz = _parsear(xml)
    for s in raiz.findall("{%s}Signature" % DS):
        raiz.remove(s)
    _limpiar(raiz)

    digest = base64.b64encode(hashlib.sha256(_c14n(raiz)).digest()).decode()

    E = lambda tag, **at: etree.SubElement(at.pop("_p"), "{%s}%s" % (DS, tag), **at)
    sig = etree.SubElement(raiz, "{%s}Signature" % DS, nsmap={None: DS})
    si = E("SignedInfo", _p=sig)
    E("CanonicalizationMethod", _p=si, Algorithm=C14N)
    E("SignatureMethod", _p=si, Algorithm=RSA_SHA256)
    ref = E("Reference", _p=si, URI="")
    tr = E("Transforms", _p=ref)
    E("Transform", _p=tr, Algorithm=ENVELOPED)
    E("DigestMethod", _p=ref, Algorithm=SHA256)
    E("DigestValue", _p=ref).text = digest

    firma = certificado.clave.sign(_c14n(si), padding.PKCS1v15(), hashes.SHA256())
    E("SignatureValue", _p=sig).text = base64.b64encode(firma).decode()
    ki = E("KeyInfo", _p=sig)
    xd = E("X509Data", _p=ki)
    E("X509Certificate", _p=xd).text = certificado.cert_base64

    return '<?xml version="1.0" encoding="utf-8"?>' + etree.tostring(raiz, encoding="unicode")


def verificar_firma(xml_firmado):
    """Comprueba digest y firma con el certificado que trae el propio XML. True/False."""
    from cryptography import x509
    raiz = _parsear(xml_firmado)
    sig = raiz.find("{%s}Signature" % DS)
    if sig is None:
        return False
    ns = {"ds": DS}
    digest = sig.findtext("ds:SignedInfo/ds:Reference/ds:DigestValue", namespaces=ns)
    valor = base64.b64decode(sig.findtext("ds:SignatureValue", namespaces=ns))
    cert = x509.load_der_x509_certificate(base64.b64decode(
        sig.findtext("ds:KeyInfo/ds:X509Data/ds:X509Certificate", namespaces=ns)))
    si = sig.find("ds:SignedInfo", ns)
    si_c14n = _c14n(si)
    raiz.remove(sig)
    if base64.b64encode(hashlib.sha256(_c14n(raiz)).digest()).decode() != digest:
        return False
    try:
        cert.public_key().verify(valor, si_c14n, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def codigo_seguridad(xml_firmado):
    """Primeros 6 caracteres del SignatureValue (va debajo del QR y en el RFCE)."""
    raiz = _parsear(xml_firmado)
    v = raiz.findtext(".//{%s}SignatureValue" % DS)
    if not v:
        raise ValueError("El XML no tiene SignatureValue")
    return v[:6]
