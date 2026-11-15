import datetime, pytest
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from diana_fiscal import Certificado


@pytest.fixture(scope="session")
def p12():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PRUEBA DIANA FISCAL")])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(k.public_key())
         .serial_number(1).not_valid_before(ahora).not_valid_after(ahora + datetime.timedelta(days=30))
         .sign(k, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b"x", k, c, None,
                                                 serialization.BestAvailableEncryption(b"1234"))


@pytest.fixture(scope="session")
def cert(p12):
    return Certificado.desde_bytes(p12, "1234")


@pytest.fixture
def factura31():
    return {
        "Encabezado": {
            "IdDoc": {"TipoeCF": 31, "eNCF": "E310000000001", "FechaVencimientoSecuencia": "31-12-2027",
                      "IndicadorMontoGravado": 0, "TipoIngresos": "01", "TipoPago": 1,
                      "TablaFormasPago": {"FormaDePago": [{"FormaPago": 1, "MontoPago": "6000.00"}]}},
            "Emisor": {"RNCEmisor": "131234567", "RazonSocialEmisor": "CANOPOLIS SRL",
                       "DireccionEmisor": "Santo Domingo", "FechaEmision": "15-11-2026"},
            "Comprador": {"RNCComprador": "101672919", "RazonSocialComprador": "Cliente Prueba SRL"},
            "Totales": {"MontoExento": "6000.00", "MontoTotal": "6000.00"},
        },
        "DetallesItems": {"Item": [
            {"NumeroLinea": 1, "IndicadorFacturacion": 4, "NombreItem": "Microchip", "IndicadorBienoServicio": 1,
             "CantidadItem": 10, "UnidadMedida": 43, "PrecioUnitarioItem": "600.00", "MontoItem": "6000.00"}]},
    }
