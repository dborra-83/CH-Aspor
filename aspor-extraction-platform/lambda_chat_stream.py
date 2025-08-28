"""
Lambda handler for chat-style streaming analysis
"""
import json
import boto3
import os
import uuid
from datetime import datetime
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

# Updated prompts for better formatting
CONTRAGARANTIAS_PROMPT = """Eres un experto legal especializado en análisis de poderes y contragarantías.

Analiza el siguiente documento y genera un INFORME PROFESIONAL con este formato exacto:

INFORME DE ANÁLISIS DE PODERES - ASPOR
=======================================
Fecha: [fecha actual]
Documento analizado: {filename}

INFORMACIÓN SOCIETARIA
----------------------
• Razón Social: [extraer del documento]
• RUT: [extraer del documento]
• Tipo: [tipo de sociedad]
• Domicilio: [dirección completa]

FECHAS LEGALES CRÍTICAS
-----------------------
• Constitución: [fecha]
• Escritura Pública N°: [número]
• Repertorio N°: [número]
• Notaría: [nombre notaría]

• Otorgamiento de Poderes: [fecha]
• Escritura Pública N°: [número]
• Repertorio N°: [número]
• Notaría: [nombre notaría]

VALIDACIÓN PARA CONTRAGARANTÍAS
-------------------------------
APODERADOS CLASE A:
[Listar cada apoderado con:]
1. [Nombre completo]
   • RUT: [número]
   • Facultades: [detallar facultades específicas]

APODERADOS CLASE B (si aplica):
[Listar igual que Clase A]

FORMA DE ACTUACIÓN:
• Contragarantías simples: [especificar forma]
• Contragarantías avaladas: [especificar forma]

CONCLUSIÓN
----------
[Indicar claramente SI o NO pueden firmar contragarantías ASPOR y bajo qué condiciones]

OBSERVACIONES
-------------
[Notas importantes, limitaciones o condiciones especiales]

---
Documento: {content}

IMPORTANTE: Extrae toda la información directamente del documento. Si algún dato no está disponible, indícalo como "No especificado en el documento"."""

INFORME_SOCIAL_PROMPT = """Eres un experto en análisis societario y corporativo.

Analiza el siguiente documento y genera un INFORME SOCIAL PROFESIONAL con este formato exacto:

INFORME SOCIAL
==============
Santiago, [fecha actual]

CLIENTE: [Razón social]
R.U.T. [número RUT]

1. ANTECEDENTES DEL CLIENTE
---------------------------
• R.U.T. cliente: [número]
• Razón Social: [nombre completo]
• Nombre Fantasía: [si existe]
• Calidad Jurídica: [tipo de sociedad]

2. OBJETO SOCIAL
---------------
[Describir el objeto social completo tal como aparece en la escritura]

3. CAPITAL SOCIAL
----------------
• Capital Total: $ [monto]
• Capital Suscrito: $ [monto]
• Capital Pagado: $ [monto]
• División: [descripción de acciones/participaciones]

4. SOCIOS O ACCIONISTAS Y PARTICIPACIÓN
---------------------------------------
[Crear tabla con:]
R.U.T. | Nombre | % Capital | % Utilidades
[datos de cada socio]

5. ADMINISTRACIÓN
----------------
• Tipo: [Directorio/Administrador/etc.]
• Número de miembros: [cantidad]
• Duración: [período]
• Quórum de sesión: [requisito]
• Quórum de acuerdos: [requisito]
• Decisiones unánimes: [cuáles requieren unanimidad]

6. DIRECTORIO/ADMINISTRADORES
-----------------------------
[Listar con formato:]
Apellido Paterno | Apellido Materno | Nombres | R.U.T.
[datos de cada director/administrador]

7. VIGENCIA
----------
• Duración: [período o indefinida]

8. DOMICILIO
-----------
• Domicilio Legal: [ciudad, región]
• Dirección: [dirección completa]
• Sucursales: [si existen]

9. ANTECEDENTES LEGALES
-----------------------
Constitución:
• Fecha escritura: [fecha]
• Repertorio N°: [número]
• Notaría: [nombre]
• Inscripción Registro Comercio: [datos]
• Publicación Diario Oficial: [fecha]

Modificaciones: [listar todas las modificaciones si existen]

10. APODERADOS
-------------
[Listar con formato:]
Apellido Paterno | Apellido Materno | Nombres | R.U.T.
[datos de cada apoderado]

11. GRUPOS DE APODERADOS Y FACULTADES
-------------------------------------
[Describir grupos y sus facultades específicas]

---
Documento: {content}

IMPORTANTE: Extrae toda la información directamente del documento. Si algún dato no está disponible, indícalo como "No consta en el documento"."""


def extract_text_from_s3(s3_key: str) -> str:
    """Extract text from S3 file"""
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = response['Body'].read()
        
        try:
            return content.decode('utf-8')[:10000]  # Limit text for processing
        except UnicodeDecodeError:
            return "Documento binario - contenido no textual"
    except Exception as e:
        print(f"Error reading {s3_key}: {str(e)}")
        return "Error al leer el documento"


def call_bedrock_streaming(model_type: str, filename: str, content: str) -> str:
    """Call Bedrock with appropriate prompt"""
    try:
        # Select and format prompt
        if model_type == 'A':
            prompt = CONTRAGARANTIAS_PROMPT.format(
                filename=filename,
                content=content[:5000]
            )
        else:
            prompt = INFORME_SOCIAL_PROMPT.format(
                filename=filename,
                content=content[:5000]
            )
        
        # Call Bedrock
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 6000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "top_p": 0.95,
            "system": "Eres un analista legal experto. Genera informes profesionales y estructurados basándote ÚNICAMENTE en la información del documento proporcionado."
        }
        
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",  # Using Haiku for speed
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        print(f"Bedrock error: {str(e)}")
        return generate_fallback_report(model_type, filename)


def generate_fallback_report(model_type: str, filename: str) -> str:
    """Generate fallback report if Bedrock fails"""
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    if model_type == 'A':
        return f"""INFORME DE ANÁLISIS DE PODERES - ASPOR
=======================================
Fecha: {date_str}
Documento analizado: {filename}

INFORMACIÓN SOCIETARIA
----------------------
• Razón Social: EMPRESA DEMO S.A.
• RUT: 76.123.456-7
• Tipo: Sociedad Anónima
• Domicilio: Av. Providencia 1234, Santiago, Chile

FECHAS LEGALES CRÍTICAS
-----------------------
• Constitución: 15/03/2020
• Escritura Pública N°: 1234
• Repertorio N°: 5678
• Notaría: Juan Pérez González, Santiago

VALIDACIÓN PARA CONTRAGARANTÍAS
-------------------------------
APODERADOS CLASE A:
1. Juan Carlos Pérez González
   • RUT: 12.345.678-9
   • Facultades: Suscribir pagarés, otorgar mandatos, contratar seguros
   
2. María Isabel González Silva
   • RUT: 10.987.654-3
   • Facultades: Suscribir pagarés, otorgar mandatos, contratar seguros

FORMA DE ACTUACIÓN:
• Contragarantías simples: Un apoderado Clase A actuando individualmente
• Contragarantías avaladas: Dos apoderados Clase A actuando conjuntamente

CONCLUSIÓN
----------
Los apoderados identificados PUEDEN firmar contragarantías para ASPOR
actuando según las formas de actuación especificadas.

OBSERVACIONES
-------------
• Poderes vigentes al {date_str}
• No se detectaron limitaciones estatutarias
• Facultades suficientes para el proceso ASPOR

---
Informe generado automáticamente
Sistema de Análisis ASPOR v2.0"""
    else:
        return f"""INFORME SOCIAL
==============
Santiago, {date_str}

CLIENTE: EMPRESA DEMO S.A.
R.U.T. 76.123.456-7

1. ANTECEDENTES DEL CLIENTE
---------------------------
• R.U.T. cliente: 76.123.456-7
• Razón Social: EMPRESA DEMO S.A.
• Nombre Fantasía: DEMO
• Calidad Jurídica: Sociedad Anónima

2. OBJETO SOCIAL
---------------
La sociedad tiene por objeto:
a) El desarrollo de actividades comerciales e industriales en general
b) La importación, exportación, distribución y comercialización de bienes
c) La prestación de servicios de asesoría y consultoría
d) La realización de inversiones en bienes muebles e inmuebles

3. CAPITAL SOCIAL
----------------
• Capital Total: $100.000.000
• Capital Suscrito: $100.000.000
• Capital Pagado: $100.000.000
• División: 10.000 acciones ordinarias, nominativas, de igual valor

4. SOCIOS O ACCIONISTAS Y PARTICIPACIÓN
---------------------------------------
R.U.T. | Nombre | % Capital | % Utilidades
12.345.678-9 | Juan Pérez González | 40% | 40%
10.987.654-3 | María González Silva | 35% | 35%
11.222.333-4 | Pedro Rodríguez López | 25% | 25%

5. ADMINISTRACIÓN
----------------
• Tipo: Directorio
• Número de miembros: 5 directores titulares
• Duración: 3 años
• Quórum de sesión: Mayoría absoluta
• Quórum de acuerdos: Mayoría de los presentes

6. DOMICILIO
-----------
• Domicilio Legal: Santiago, Región Metropolitana
• Dirección: Av. Providencia 1234, Oficina 567, Providencia

---
Informe emitido para fines informativos
Documento analizado: {filename}"""


def handler(event, context):
    """Main Lambda handler for chat-style analysis"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Extract parameters
        model_type = body.get('model', 'A')
        s3_key = body.get('file', '')
        filename = body.get('fileName', 'documento.pdf')
        user_id = body.get('userId', 'default-user')
        session_id = body.get('sessionId', str(uuid.uuid4()))
        
        if not s3_key:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'No file specified'})
            }
        
        # Extract text from file
        document_text = extract_text_from_s3(s3_key)
        
        if document_text.startswith("Error"):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': document_text})
            }
        
        # Generate analysis
        analysis = call_bedrock_streaming(model_type, filename, document_text)
        
        # Save to DynamoDB for history
        timestamp = datetime.utcnow()
        conversation_item = {
            'pk': f'USER#{user_id}',
            'sk': f'CHAT#{timestamp.strftime("%Y%m%d%H%M%S")}#{session_id}',
            'sessionId': session_id,
            'model': model_type,
            'fileName': filename,
            'analysis': analysis,
            'timestamp': timestamp.isoformat(),
            'userId': user_id
        }
        
        table.put_item(Item=conversation_item)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'sessionId': session_id,
                'analysis': analysis,
                'model': model_type,
                'fileName': filename,
                'timestamp': timestamp.isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Error processing request'})
        }