"""Diana Fiscal: facturación electrónica e-CF directa con la DGII (República Dominicana).

Módulos:
  certificado  leer el certificado .p12 de firma digital
  firma        firmar XML (XMLDSig RSA-SHA256, C14N) como exige la DGII
  ecf          armar el XML del e-CF a partir de un diccionario
  rfce         resumen de factura de consumo (E32 < RD$250,000)
  documentos   anulación de secuencias (ANECF), aprobación comercial (ACECF), acuse de recibo (ARECF)
  dgii         cliente de los servicios web de la DGII (semilla, token, envío, consultas)
  qr           enlaces del código QR y código de seguridad
  receptor     servidor emisor-receptor para recibir e-CF de suplidores
"""
__version__ = "0.1.0"

from .certificado import Certificado
from .firma import firmar_xml, verificar_firma, codigo_seguridad
from .ecf import construir_ecf, nombre_archivo
from .rfce import ecf32_a_rfce, es_resumen
from .dgii import ClienteDGII, Ambiente
from . import qr, documentos
