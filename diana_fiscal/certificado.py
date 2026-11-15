"""Lectura del certificado digital .p12 / .pfx (DigiFirma, Avansi, etc.)."""
from dataclasses import dataclass
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography import x509


@dataclass
class Certificado:
    clave: object          # llave privada (cryptography)
    cert: x509.Certificate

    @classmethod
    def desde_archivo(cls, ruta, contrasena):
        with open(ruta, "rb") as f:
            return cls.desde_bytes(f.read(), contrasena)

    @classmethod
    def desde_bytes(cls, datos, contrasena):
        if isinstance(contrasena, str):
            contrasena = contrasena.encode()
        clave, cert, _ = pkcs12.load_key_and_certificates(datos, contrasena)
        if clave is None or cert is None:
            raise ValueError("El archivo .p12 no trae llave privada y certificado")
        return cls(clave, cert)

    @property
    def cert_base64(self):
        import base64
        return base64.b64encode(self.cert.public_bytes(Encoding.DER)).decode()

    @property
    def vence(self):
        return self.cert.not_valid_after_utc

    @property
    def titular(self):
        return self.cert.subject.rfc4514_string()

    def clave_pem(self):
        return self.clave.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
