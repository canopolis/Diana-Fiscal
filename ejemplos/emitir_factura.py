"""Ejemplo: emitir una Factura de Crédito Fiscal (E31) exenta en el ambiente de PRUEBAS.
Uso: python ejemplos/emitir_factura.py ruta\\firma.p12 contraseña
"""
import sys, json
from diana_fiscal import Certificado, Ambiente
from diana_fiscal.facturador import Facturador

cert = Certificado.desde_archivo(sys.argv[1], sys.argv[2])
print("Certificado de:", cert.titular, "vence:", cert.vence)

factura = {
    "Encabezado": {
        "IdDoc": {"TipoeCF": 31, "eNCF": "E310000000001", "FechaVencimientoSecuencia": "31-12-2027",
                  "IndicadorMontoGravado": 0, "TipoIngresos": "01", "TipoPago": 1,
                  "TablaFormasPago": {"FormaDePago": [{"FormaPago": 1, "MontoPago": "6000.00"}]}},
        "Emisor": {"RNCEmisor": "RNC_DE_CANOPOLIS", "RazonSocialEmisor": "CANOPOLIS",
                   "DireccionEmisor": "Santo Domingo", "FechaEmision": "15-11-2026"},
        "Comprador": {"RNCComprador": "101672919", "RazonSocialComprador": "CLIENTE"},
        "Totales": {"MontoExento": "6000.00", "MontoTotal": "6000.00"},
    },
    "DetallesItems": {"Item": [
        {"NumeroLinea": 1, "IndicadorFacturacion": 4, "NombreItem": "Microchip", "IndicadorBienoServicio": 1,
         "CantidadItem": 10, "PrecioUnitarioItem": "600.00", "MontoItem": "6000.00"}]},
}

r = Facturador(cert, Ambiente.PRUEBAS, carpeta="ecf_pruebas").emitir(factura)
print(json.dumps({k: r[k] for k in ("encf", "estado", "codigo_seguridad", "qr")}, ensure_ascii=False, indent=2))
