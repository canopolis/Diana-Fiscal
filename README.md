# Diana Fiscal

Facturación electrónica **e-CF** directa con la **DGII** (República Dominicana), en Python,
para usarse dentro de **Diana** sin depender de proveedores externos.

Hace lo mismo que la librería [dgii-ecf](https://github.com/victors1681/dgii-ecf) (Node, MIT),
reescrito en Python:

| Función | Módulo |
|---|---|
| Leer certificado .p12 | `certificado.py` |
| Firma XML (RSA-SHA256, C14N, enveloped) | `firma.py` |
| Armar XML e-CF (E31, E32, E33, E34, E41, E43, E44, E45, E46, E47) | `ecf.py` |
| Resumen RFCE (E32 < RD$250,000) | `rfce.py` |
| Código de seguridad y enlaces QR | `firma.py`, `qr.py` |
| Semilla → token, envío, TrackId, consulta de estado, directorio | `dgii.py` |
| Anulación de secuencias (ANECF), aprobación comercial (ACECF), acuse (ARECF) | `documentos.py` |
| Flujo completo emitir (firma, decide resumen o e-CF, envía, espera resultado, guarda XML) | `facturador.py` |
| Servidor receptor para recibir e-CF de suplidores | `receptor.py` |

Ambientes: `TesteCF` (pruebas), `CerteCF` (certificación), `eCF` (producción).

## Pasos para quedar habilitado ante la DGII
1. Certificado digital de persona física representante (DigiFirma, Avansi u otro autorizado) en `.p12`.
2. Solicitud de facturador electrónico en la Oficina Virtual de la DGII.
3. Set de pruebas en `TesteCF` y certificación en `CerteCF` (la DGII envía los casos).
4. Declaración de cumplimiento y paso a `eCF` (producción).

## Pruebas
`python -m pytest -q tests` — la firma se verifica además con una librería independiente (signxml).
