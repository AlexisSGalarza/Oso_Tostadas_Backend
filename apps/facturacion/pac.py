"""Timbrado del CFDI con un PAC (proveedor autorizado de certificacion).

Hay dos implementaciones y se elige con CFDI_PAC en el .env:

- `simulado` (por defecto): no llama a nadie. Agrega al XML un timbre de mentira
  para poder probar el flujo completo. Esas facturas NO tienen validez fiscal.
- `finkok`: manda el XML a Finkok con `sign_stamp`, que lo sella con el CSD que
  el emisor subio a su cuenta de Finkok y lo timbra ante el SAT. Requiere
  FINKOK_USUARIO y FINKOK_PASSWORD. Con FINKOK_URL apuntando a
  demo-facturacion.finkok.com es el ambiente de pruebas de Finkok; con
  facturacion.finkok.com es produccion.
"""
import base64
import uuid
from dataclasses import dataclass
from urllib import error, request
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from defusedxml import ElementTree as SafeET
from django.conf import settings
from django.utils import timezone

from .cfdi import NS_CFDI

NS_TFD = 'http://www.sat.gob.mx/TimbreFiscalDigital'
ET.register_namespace('tfd', NS_TFD)


class ErrorTimbrado(Exception):
    """El PAC rechazo el comprobante o no se pudo contactar."""


@dataclass
class Timbre:
    folio_fiscal: str
    xml: str
    modo: str  # 'pruebas' | 'produccion'


class PacSimulado:
    modo = 'pruebas'

    def timbrar(self, xml: str) -> Timbre:
        folio_fiscal = str(uuid.uuid4()).upper()
        raiz = SafeET.fromstring(xml)
        complemento = ET.SubElement(raiz, f'{{{NS_CFDI}}}Complemento')
        ET.SubElement(complemento, f'{{{NS_TFD}}}TimbreFiscalDigital', {
            'Version': '1.1',
            'UUID': folio_fiscal,
            'FechaTimbrado': timezone.localtime().strftime('%Y-%m-%dT%H:%M:%S'),
            'RfcProvCertif': 'SIMULADO00000',
            'SelloCFD': 'SIMULADO-SIN-VALIDEZ-FISCAL',
            'NoCertificadoSAT': '00000000000000000000',
            'SelloSAT': 'SIMULADO-SIN-VALIDEZ-FISCAL',
        })
        return Timbre(folio_fiscal, ET.tostring(raiz, encoding='unicode', xml_declaration=True), self.modo)


class PacFinkok:
    def __init__(self):
        self.url = settings.FINKOK_URL.rstrip('/')
        self.usuario = settings.FINKOK_USUARIO
        self.password = settings.FINKOK_PASSWORD
        self.modo = 'pruebas' if 'demo-' in self.url else 'produccion'

    def timbrar(self, xml: str) -> Timbre:
        if not self.usuario or not self.password:
            raise ErrorTimbrado('Faltan FINKOK_USUARIO y FINKOK_PASSWORD en la configuracion.')

        sobre = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:apps="http://facturacion.finkok.com/stamp">'
            '<soapenv:Header/><soapenv:Body><apps:sign_stamp>'
            f'<apps:xml>{base64.b64encode(xml.encode("utf-8")).decode("ascii")}</apps:xml>'
            f'<apps:username>{escape(self.usuario)}</apps:username>'
            f'<apps:password>{escape(self.password)}</apps:password>'
            '</apps:sign_stamp></soapenv:Body></soapenv:Envelope>'
        )
        peticion = request.Request(
            f'{self.url}/servicios/soap/stamp',
            data=sobre.encode('utf-8'),
            headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': 'sign_stamp'},
        )
        try:
            with request.urlopen(peticion, timeout=30) as respuesta:
                cuerpo = respuesta.read()
        except error.HTTPError as exc:
            cuerpo = exc.read()
        except OSError as exc:
            raise ErrorTimbrado(f'No se pudo contactar al PAC: {exc}') from exc

        return self._leer_respuesta(cuerpo)

    def _leer_respuesta(self, cuerpo: bytes) -> Timbre:
        try:
            raiz = SafeET.fromstring(cuerpo)
        except Exception as exc:
            raise ErrorTimbrado('El PAC devolvio una respuesta que no se pudo leer.') from exc

        # La respuesta trae namespaces propios de Finkok; se busca por nombre local.
        valores = {}
        for nodo in raiz.iter():
            nombre = nodo.tag.rsplit('}', 1)[-1]
            if nodo.text and nodo.text.strip() and nombre not in valores:
                valores[nombre] = nodo.text.strip()

        folio_fiscal = valores.get('UUID')
        xml_timbrado = valores.get('xml')
        if not folio_fiscal or not xml_timbrado:
            motivo = valores.get('MensajeIncidencia') or valores.get('faultstring') or 'sin detalle'
            codigo = valores.get('CodigoError')
            raise ErrorTimbrado(f'El PAC rechazo la factura: {f"[{codigo}] " if codigo else ""}{motivo}')
        return Timbre(folio_fiscal.upper(), xml_timbrado, self.modo)


def obtener_pac():
    if settings.CFDI_PAC == 'finkok':
        return PacFinkok()
    return PacSimulado()


def modo_actual() -> str:
    return obtener_pac().modo
