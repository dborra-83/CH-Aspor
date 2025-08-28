"""
Unified Lambda handler for ASPOR platform - All code in one file for AWS Lambda
"""
import json
import boto3
import os
import io
import zipfile
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import uuid
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')
textract_client = boto3.client('textract')

# Environment variables
table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

# Configuration
REGION = 'us-east-1'
BEDROCK_MODEL = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Using Claude 3 Sonnet (works with on-demand)
MAX_FILES_PER_RUN = 3
MAX_FILE_SIZE_MB = 25
ALLOWED_EXTENSIONS = ['pdf', 'docx', 'doc', 'txt']


def sanitize_user_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return ""
    # Remove null bytes and control characters
    text = text.replace('\x00', '')
    text = re.sub(r'[\x01-\x1f\x7f-\x9f]', '', text)
    # Limit length
    return text[:100000]


def escape_html(text: str) -> str:
    """Escape HTML/XML special characters"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def validate_file(file_key: str) -> Tuple[bool, Optional[str]]:
    """Validate file key for security"""
    if not file_key:
        return False, "File key is required"
    
    # Check for path traversal
    if '..' in file_key or file_key.startswith('/'):
        return False, "Invalid file path"
    
    # For uploaded files without extension (like uploads/xxx/file_1), allow them
    if 'uploads/' in file_key and '/file_' in file_key:
        return True, None
    
    # Check extension for other files
    if '.' in file_key:
        ext = file_key.split('.')[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File type not allowed: {ext}"
    
    return True, None


def extract_text_from_s3(s3_key: str) -> str:
    """Extract text content from S3 file using Textract for PDFs"""
    try:
        # Validate file first
        is_valid, error = validate_file(s3_key)
        if not is_valid:
            return f"Error: {error}"
        
        print(f"Extracting text from: {s3_key}")
        
        # For PDFs and images, use Textract (synchronous only for speed)
        if not '.' in s3_key or s3_key.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            print(f"Using Textract for file: {s3_key}")
            try:
                # Use synchronous detection for single-page documents
                textract_response = textract_client.detect_document_text(
                    Document={
                        'S3Object': {
                            'Bucket': bucket_name,
                            'Name': s3_key
                        }
                    }
                )
                
                extracted_text = ""
                blocks = textract_response.get('Blocks', [])
                print(f"Textract returned {len(blocks)} blocks")
                
                for item in blocks:
                    if item['BlockType'] == 'LINE':
                        text = item.get('Text', '')
                        if text:
                            extracted_text += text + '\n'
                
                if extracted_text:
                    print(f"Extracted {len(extracted_text)} characters from document")
                    return sanitize_user_input(extracted_text[:10000])
                else:
                    print(f"No text extracted from {s3_key}, trying as binary")
                    
            except Exception as textract_error:
                error_str = str(textract_error)
                print(f"Textract error: {error_str}")
                
                # If it's a PDF that Textract can't handle with detect_document_text,
                # return a message indicating we need the text content
                if 'UnsupportedDocumentException' in error_str or 'InvalidParameterException' in error_str:
                    return """NOTA: El documento PDF no pudo ser procesado directamente con OCR.
                    
Para documentos PDF complejos, por favor asegúrese de que:
1. El PDF contenga texto seleccionable (no solo imágenes escaneadas)
2. El documento no esté protegido con contraseña
3. El archivo no exceda los 5MB de tamaño

Alternativamente, puede convertir el documento a formato de texto antes de subirlo."""
                
                # For other errors, try reading as binary
                pass
        
        # For text files or if Textract fails, try direct reading
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = response['Body'].read()
        
        # Try to decode as text
        try:
            text = content.decode('utf-8')
            print(f"Read {len(text)} characters as UTF-8 from {s3_key}")
            return sanitize_user_input(text)
        except UnicodeDecodeError:
            # Try Latin-1 encoding
            try:
                text = content.decode('latin-1')
                print(f"Read {len(text)} characters as Latin-1 from {s3_key}")
                return sanitize_user_input(text)
            except:
                print(f"Could not decode {s3_key} as text")
                return "No se pudo leer el contenido del documento."
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print(f"File not found: {s3_key}")
            return "Archivo no encontrado."
        else:
            print(f"S3 error reading {s3_key}: {str(e)}")
            return "Error al leer el documento."
    except Exception as e:
        print(f"Unexpected error reading {s3_key}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return "Error procesando el documento."


# Mock report function removed to ensure real Bedrock processing


def call_bedrock(model_type: str, text: str, file_names: list) -> str:
    """Call Bedrock API with proper error handling"""
    try:
        # Sanitize input text
        text = sanitize_user_input(text)
        
        # Use more text for analysis (up to 10000 characters)
        text_for_analysis = text[:10000]
        
        # Create prompt based on model type
        if model_type == 'A':
            # Complete CONTRAGARANTIAS prompt
            prompt = f"""Eres un asistente especializado en análisis legal de escrituras públicas para ASPOR, enfocado en validar capacidad de firma de contragarantías.

CONTEXTO CRÍTICO:
- Proceso ASPOR: Cuando cobran una póliza por incumplimiento, necesitan repetir contra el afianzado
- Contragarantía: Es un mandato que permite suscribir pagarés para facilitar cobro ejecutivo
- Objetivo: Identificar quién puede firmar contragarantías según sus facultades legales

Documentos analizados: {', '.join(file_names) if file_names else 'Documentos'}

Contenido:
{text_for_analysis}

ANALIZA Y GENERA UN INFORME DETALLADO CON:

1. IDENTIFICACIÓN SOCIETARIA
- Razón social completa y RUT
- Tipo societario y domicilio legal

2. FECHAS LEGALES Y DATOS NOTARIALES
- Fecha constitución de la sociedad
- Fecha otorgamiento de poderes
- Fecha certificado de vigencia
- CRÍTICO: Verificar vencimiento de poderes

3. FACULTADES ESPECÍFICAS REQUERIDAS
Para Contragarantía Simple:
- Facultades cambiarias (girar, suscribir pagarés)
- Otorgar mandatos
- Contratar seguros

Para Contragarantía Avalada:
- Constituir aval o fianza solidaria
- Verificar limitaciones societarias

4. ANÁLISIS DE APODERADOS POR CLASE
- Identificar clases (A, B, C, etc.)
- Listar apoderados con sus facultades específicas
- Indicar quiénes pueden firmar contragarantías

5. CONCLUSIÓN EJECUTIVA
- Resumen claro de quién puede firmar
- Tipo de contragarantía autorizada
- Observaciones críticas"""
        else:
            # Complete INFORMES SOCIALES prompt
            prompt = f"""Eres un asistente especializado en análisis de escrituras societarias para generar informes profesionales.

Documentos analizados: {', '.join(file_names) if file_names else 'Documentos'}

Contenido:
{text_for_analysis}

GENERA UN INFORME SOCIAL PROFESIONAL CON:

1. IDENTIFICACIÓN SOCIETARIA
- Razón social completa
- RUT
- Tipo de sociedad
- Domicilio legal

2. CONSTITUCIÓN Y MODIFICACIONES
- Fecha de constitución
- Escritura pública (número, fecha, notaría)
- Inscripciones en Conservador
- Modificaciones relevantes

3. OBJETO SOCIAL
- Objeto principal
- Actividades autorizadas
- Restricciones

4. CAPITAL SOCIAL
- Capital inicial
- Capital actual
- Forma de pago

5. COMPOSICIÓN SOCIETARIA
- Socios actuales
- Porcentaje de participación
- Derechos especiales

6. ADMINISTRACIÓN Y REPRESENTACIÓN
- Estructura administrativa
- Representantes legales
- Apoderados principales
- Facultades otorgadas

7. VIGENCIA Y ESTADO
- Estado societario actual
- Certificados de vigencia
- Observaciones relevantes"""
        
        # Call Bedrock with more tokens for complete analysis
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "top_p": 0.95
        }
        
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        error_msg = f"Bedrock processing error: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        
        # Return error message instead of mock data
        return f"""ERROR EN PROCESAMIENTO

⚠️ No se pudo procesar el documento con Bedrock.

Error técnico: {str(e)[:200]}

Por favor, contacte al soporte técnico si el problema persiste.

Documentos intentados: {', '.join(file_names) if file_names else 'Sin archivos'}

Nota: Este es un mensaje de error real, no datos de prueba."""


def create_docx(text: str, title: str = "INFORME ASPOR") -> bytes:
    """Create a valid DOCX file"""
    # Escape XML special characters
    text = escape_html(text)
    
    # Split text into paragraphs
    paragraphs = text.split('\n')
    
    # Create paragraph XML
    paragraphs_xml = ""
    for para in paragraphs:
        if para.strip():
            if para.isupper() or '======' in para or '------' in para:
                # Header styling
                paragraphs_xml += f'''<w:p>
                    <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
                    <w:r><w:rPr><w:b/></w:rPr><w:t>{para.strip()}</w:t></w:r>
                </w:p>'''
            else:
                # Normal paragraph
                paragraphs_xml += f'''<w:p>
                    <w:r><w:t>{para}</w:t></w:r>
                </w:p>'''
        else:
            paragraphs_xml += '<w:p/>'
    
    # DOCX structure files
    docx_files = {
        '[Content_Types].xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>''',
        
        '_rels/.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''',
        
        'word/_rels/document.xml.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        
        'word/styles.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:style w:type="paragraph" w:styleId="Normal">
        <w:name w:val="Normal"/>
        <w:rPr>
            <w:sz w:val="24"/>
        </w:rPr>
    </w:style>
    <w:style w:type="paragraph" w:styleId="Heading1">
        <w:name w:val="Heading 1"/>
        <w:basedOn w:val="Normal"/>
        <w:pPr>
            <w:spacing w:before="240" w:after="120"/>
        </w:pPr>
        <w:rPr>
            <w:b/>
            <w:sz w:val="32"/>
        </w:rPr>
    </w:style>
</w:styles>''',
        
        'word/document.xml': f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:pPr><w:jc w:val="center"/></w:pPr>
            <w:r>
                <w:rPr><w:b/><w:sz w:val="40"/></w:rPr>
                <w:t>{escape_html(title)}</w:t>
            </w:r>
        </w:p>
        <w:p/>
        {paragraphs_xml}
        <w:sectPr>
            <w:pgSz w:w="11906" w:h="16838"/>
            <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
        </w:sectPr>
    </w:body>
</w:document>'''
    }
    
    # Create DOCX in memory
    docx_buffer = io.BytesIO()
    with zipfile.ZipFile(docx_buffer, 'w', zipfile.ZIP_DEFLATED) as docx:
        for file_path, content in docx_files.items():
            docx.writestr(file_path, content)
    
    return docx_buffer.getvalue()


def create_pdf(text: str, title: str = "INFORME ASPOR") -> bytes:
    """Create a simple valid PDF file"""
    # Clean text for PDF
    text = text.replace('(', '\\(').replace(')', '\\)').replace('\\', '\\\\')
    lines = text.split('\n')
    
    # Create PDF content stream
    content_lines = []
    y_position = 750
    
    # Add title
    content_lines.append('BT')
    content_lines.append('/F1 16 Tf')
    content_lines.append(f'50 {y_position} Td')
    content_lines.append(f'({title}) Tj')
    content_lines.append('ET')
    y_position -= 30
    
    # Add content (limited to fit on page)
    for line in lines[:50]:
        if line.strip() and y_position > 50:
            line_clean = line[:80]
            content_lines.append('BT')
            content_lines.append('/F1 10 Tf')
            content_lines.append(f'50 {y_position} Td')
            content_lines.append(f'({line_clean}) Tj')
            content_lines.append('ET')
            y_position -= 15
    
    content_stream = '\n'.join(content_lines)
    
    # Build PDF structure
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
/Contents 4 0 R >>
endobj
4 0 obj
<< /Length {len(content_stream)} >>
stream
{content_stream}
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000274 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
{274 + len(content_stream) + 25}
%%EOF"""
    
    return pdf_content.encode('latin-1', errors='ignore')


def generate_output_file(text: str, format_type: str, model: str) -> Tuple[bytes, str]:
    """Generate output file in requested format"""
    title = "INFORME DE CONTRAGARANTÍAS" if model == 'A' else "INFORME SOCIAL"
    
    if format_type == 'docx':
        content = create_docx(text, title)
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif format_type == 'pdf':
        content = create_pdf(text, title)
        content_type = 'application/pdf'
    else:  # txt
        content = text.encode('utf-8')
        content_type = 'text/plain; charset=utf-8'
    
    return content, content_type


def handler(event, context):
    """Main Lambda handler with improved error handling and security"""
    run_id = None
    timestamp = None
    user_id = 'default-user'
    
    try:
        # Parse and validate request
        body = json.loads(event.get('body', '{}'))
        
        # Validate inputs
        model = body.get('model', 'A')
        if model not in ['A', 'B']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid model type'})
            }
        
        files = body.get('files', [])
        if not files or len(files) > MAX_FILES_PER_RUN:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Must provide 1-{MAX_FILES_PER_RUN} files'})
            }
        
        # Validate all files
        for file_key in files:
            is_valid, error = validate_file(file_key)
            if not is_valid:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': f'Invalid file: {error}'})
                }
        
        file_names = body.get('fileNames', [])
        output_format = body.get('outputFormat', 'docx')
        if output_format not in ['docx', 'pdf', 'txt']:
            output_format = 'docx'
        
        user_id = body.get('userId', 'default-user')[:100]  # Limit user ID length
        
        print(f"Processing: Model={model}, Files={len(files)}, Format={output_format}")
        
        # Create run in DynamoDB
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}',
            'runId': run_id,
            'model': model,
            'files': files[:MAX_FILES_PER_RUN],
            'fileNames': file_names[:MAX_FILES_PER_RUN] if file_names else ['documento.pdf'],
            'outputFormat': output_format,
            'status': 'PROCESSING',
            'startedAt': timestamp.isoformat(),
            'userId': user_id
        }
        
        table.put_item(Item=run_item)
        
        # Extract text from all files with more content
        all_text = ""
        for i, s3_key in enumerate(files[:MAX_FILES_PER_RUN]):
            print(f"Extracting text from file {i+1}: {s3_key}")
            text = extract_text_from_s3(s3_key)
            if text and text != "Error al leer el documento.":
                file_label = file_names[i] if i < len(file_names) else f"Archivo {i+1}"
                # Use more text per file (up to 5000 chars per file)
                all_text += f"\n--- {file_label} ---\n{text[:5000]}\n"
                print(f"Extracted {len(text)} characters from {file_label}")
            else:
                print(f"Failed to extract text from file {i+1}: {s3_key}")
        
        if not all_text:
            all_text = "Contenido del documento para análisis."
        
        # Process with Bedrock or generate mock
        analysis_result = call_bedrock(model, all_text, file_names)
        
        # Save analysis text for reference
        analysis_key = f'outputs/{run_id}/analysis.txt'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=analysis_key,
            Body=analysis_result.encode('utf-8'),
            ContentType='text/plain; charset=utf-8',
            ServerSideEncryption='AES256',
            Metadata={'run_id': run_id, 'model': model}
        )
        
        # Generate output file
        output_key = f'outputs/{run_id}/report.{output_format}'
        content, content_type = generate_output_file(analysis_result, output_format, model)
        
        # Save to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=content,
            ContentType=content_type,
            ServerSideEncryption='AES256',
            Metadata={'run_id': run_id, 'model': model, 'format': output_format}
        )
        
        # Generate download URL
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': output_key,
                'ResponseContentDisposition': f'attachment; filename="report.{output_format}"'
            },
            ExpiresIn=3600
        )
        
        # Update DynamoDB with completion
        table.update_item(
            Key={
                'pk': f'USER#{user_id}',
                'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
            },
            UpdateExpression='SET #status = :status, #output = :output, #endedAt = :endedAt',
            ExpressionAttributeNames={
                '#status': 'status',
                '#output': 'output',
                '#endedAt': 'endedAt'
            },
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':output': {
                    'downloadUrl': download_url,
                    output_format: output_key
                },
                ':endedAt': datetime.utcnow().isoformat()
            }
        )
        
        print(f"Run completed successfully: {run_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'runId': run_id,
                'status': 'COMPLETED',
                'downloadUrl': download_url,
                'outputFormat': output_format,
                'message': 'Procesamiento completado exitosamente'
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error in handler: {error_msg}")
        
        # Update run status to failed if we have a run_id
        if run_id and timestamp:
            try:
                table.update_item(
                    Key={
                        'pk': f'USER#{user_id}',
                        'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
                    },
                    UpdateExpression='SET #status = :status, #error = :error, #endedAt = :endedAt',
                    ExpressionAttributeNames={
                        '#status': 'status',
                        '#error': 'error',
                        '#endedAt': 'endedAt'
                    },
                    ExpressionAttributeValues={
                        ':status': 'FAILED',
                        ':error': error_msg[:500],
                        ':endedAt': datetime.utcnow().isoformat()
                    }
                )
            except:
                pass
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Error en el procesamiento',
                'details': error_msg[:200] if not os.environ.get('PRODUCTION') else None,
                'runId': run_id
            })
        }