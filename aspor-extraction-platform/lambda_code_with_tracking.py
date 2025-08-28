"""
Lambda handler for ASPOR platform with complete processing tracking
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
import time

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
BEDROCK_MODEL = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Claude 3 Sonnet (on-demand)
MAX_FILES_PER_RUN = 3
MAX_FILE_SIZE_MB = 25
ALLOWED_EXTENSIONS = ['pdf', 'docx', 'doc', 'txt', 'png', 'jpg', 'jpeg']

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
}


def update_processing_status(run_id: str, user_id: str, timestamp: datetime, updates: dict):
    """Update processing status in DynamoDB"""
    try:
        # Build update expression
        update_expr = "SET "
        expr_attrs = {}
        expr_values = {}
        
        for key, value in updates.items():
            attr_name = f"#{key}"
            attr_value = f":{key}"
            update_expr += f"{attr_name} = {attr_value}, "
            expr_attrs[attr_name] = key
            expr_values[attr_value] = value
        
        # Add last updated timestamp
        update_expr += "#lastUpdated = :lastUpdated"
        expr_attrs["#lastUpdated"] = "lastUpdated"
        expr_values[":lastUpdated"] = datetime.utcnow().isoformat()
        
        table.update_item(
            Key={
                'pk': f'USER#{user_id}',
                'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
            },
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attrs,
            ExpressionAttributeValues=expr_values
        )
        print(f"Updated DynamoDB with: {updates}")
    except Exception as e:
        print(f"Error updating status: {str(e)}")


def sanitize_user_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return ""
    # Remove control characters but keep Spanish characters
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    # Limit length
    return text[:50000]  # Allow 50k chars for processing


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


def extract_text_from_s3(s3_key: str, run_id: str, user_id: str, timestamp: datetime) -> Tuple[str, dict]:
    """Extract text from S3 file with detailed tracking"""
    extraction_details = {
        'extractionStarted': datetime.utcnow().isoformat(),
        'extractionMethod': None,
        'extractionSuccess': False,
        'extractedCharacters': 0,
        'extractionError': None
    }
    
    try:
        # Validate file first
        is_valid, error = validate_file(s3_key)
        if not is_valid:
            extraction_details['extractionError'] = error
            update_processing_status(run_id, user_id, timestamp, {
                'processingSteps': extraction_details
            })
            return f"Error: {error}", extraction_details
        
        print(f"Starting extraction from: {s3_key}")
        
        # Check if it's a PDF or image that needs OCR
        needs_ocr = (not '.' in s3_key or 
                     s3_key.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')))
        
        if needs_ocr:
            print(f"File needs OCR processing: {s3_key}")
            extraction_details['extractionMethod'] = 'textract'
            
            # Update status: starting Textract
            update_processing_status(run_id, user_id, timestamp, {
                'textractStarted': True,
                'textractStatus': 'PROCESSING'
            })
            
            try:
                # For scanned PDFs and complex documents, use async Textract
                if s3_key.lower().endswith('.pdf') or 'uploads/' in s3_key:
                    print("Using async Textract for PDF/document")
                    
                    # Start async document analysis
                    start_response = textract_client.start_document_text_detection(
                        DocumentLocation={
                            'S3Object': {
                                'Bucket': bucket_name,
                                'Name': s3_key
                            }
                        }
                    )
                    
                    job_id = start_response['JobId']
                    print(f"Started Textract job: {job_id}")
                    
                    # Update with job ID
                    update_processing_status(run_id, user_id, timestamp, {
                        'textractJobId': job_id
                    })
                    
                    # Poll for completion (max 60 seconds for better handling)
                    max_wait = 60
                    wait_time = 0
                    
                    while wait_time < max_wait:
                        result = textract_client.get_document_text_detection(JobId=job_id)
                        status = result['JobStatus']
                        
                        if status == 'SUCCEEDED':
                            print(f"Textract job completed successfully")
                            extracted_text = ""
                            
                            # Process all blocks
                            for block in result.get('Blocks', []):
                                if block['BlockType'] == 'LINE':
                                    text = block.get('Text', '')
                                    if text:
                                        extracted_text += text + '\n'
                            
                            # Get additional pages if available
                            next_token = result.get('NextToken')
                            page_count = 1
                            
                            while next_token and len(extracted_text) < 30000:
                                page_count += 1
                                result = textract_client.get_document_text_detection(
                                    JobId=job_id,
                                    NextToken=next_token
                                )
                                for block in result.get('Blocks', []):
                                    if block['BlockType'] == 'LINE':
                                        text = block.get('Text', '')
                                        if text:
                                            extracted_text += text + '\n'
                                next_token = result.get('NextToken')
                            
                            if extracted_text:
                                extraction_details['extractionSuccess'] = True
                                extraction_details['extractedCharacters'] = len(extracted_text)
                                extraction_details['pagesProcessed'] = page_count
                                
                                # Save extracted text to DynamoDB
                                update_processing_status(run_id, user_id, timestamp, {
                                    'textractSuccess': True,
                                    'textractStatus': 'COMPLETED',
                                    'extractedTextLength': len(extracted_text),
                                    'extractedTextPreview': extracted_text[:500],  # Save preview
                                    'pagesProcessed': page_count,
                                    'processingSteps': extraction_details
                                })
                                
                                # Also save full text to S3 for reference
                                text_key = f'extracted/{run_id}/extracted_text.txt'
                                s3_client.put_object(
                                    Bucket=bucket_name,
                                    Key=text_key,
                                    Body=extracted_text.encode('utf-8'),
                                    ContentType='text/plain; charset=utf-8'
                                )
                                
                                update_processing_status(run_id, user_id, timestamp, {
                                    'extractedTextS3Key': text_key
                                })
                                
                                print(f"Extracted {len(extracted_text)} characters from {page_count} pages")
                                return sanitize_user_input(extracted_text), extraction_details
                            break
                        
                        elif status == 'FAILED':
                            error_msg = result.get('StatusMessage', 'Unknown error')
                            extraction_details['extractionError'] = error_msg
                            update_processing_status(run_id, user_id, timestamp, {
                                'textractSuccess': False,
                                'textractStatus': 'FAILED',
                                'textractError': error_msg
                            })
                            print(f"Textract job failed: {error_msg}")
                            break
                        
                        # Still processing
                        time.sleep(3)
                        wait_time += 3
                    
                    if wait_time >= max_wait:
                        extraction_details['extractionError'] = 'Textract timeout'
                        update_processing_status(run_id, user_id, timestamp, {
                            'textractSuccess': False,
                            'textractStatus': 'TIMEOUT'
                        })
                
                else:
                    # For images, use sync detection
                    print("Using sync Textract for image")
                    textract_response = textract_client.detect_document_text(
                        Document={
                            'S3Object': {
                                'Bucket': bucket_name,
                                'Name': s3_key
                            }
                        }
                    )
                    
                    extracted_text = ""
                    for block in textract_response.get('Blocks', []):
                        if block['BlockType'] == 'LINE':
                            text = block.get('Text', '')
                            if text:
                                extracted_text += text + '\n'
                    
                    if extracted_text:
                        extraction_details['extractionSuccess'] = True
                        extraction_details['extractedCharacters'] = len(extracted_text)
                        
                        update_processing_status(run_id, user_id, timestamp, {
                            'textractSuccess': True,
                            'textractStatus': 'COMPLETED',
                            'extractedTextLength': len(extracted_text),
                            'extractedTextPreview': extracted_text[:500]
                        })
                        
                        return sanitize_user_input(extracted_text), extraction_details
                
            except Exception as textract_error:
                error_str = str(textract_error)
                extraction_details['extractionError'] = error_str[:200]
                
                update_processing_status(run_id, user_id, timestamp, {
                    'textractSuccess': False,
                    'textractError': error_str[:500]
                })
                
                print(f"Textract error: {error_str}")
                
                # Return informative message
                if 'UnsupportedDocumentException' in error_str:
                    return "El documento no es compatible con OCR directo. Por favor, use un PDF con texto seleccionable.", extraction_details
        
        # Try direct text reading for text files
        extraction_details['extractionMethod'] = 'direct_read'
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = response['Body'].read()
        
        # Try to decode as text
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                text = content.decode(encoding)
                extraction_details['extractionSuccess'] = True
                extraction_details['extractedCharacters'] = len(text)
                extraction_details['encoding'] = encoding
                
                update_processing_status(run_id, user_id, timestamp, {
                    'textExtractionSuccess': True,
                    'extractedTextLength': len(text),
                    'extractedTextPreview': text[:500]
                })
                
                print(f"Read {len(text)} characters as {encoding}")
                return sanitize_user_input(text), extraction_details
            except UnicodeDecodeError:
                continue
        
        extraction_details['extractionError'] = 'Could not decode file as text'
        return "No se pudo leer el contenido del documento.", extraction_details
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        extraction_details['extractionError'] = f"S3 error: {error_code}"
        
        update_processing_status(run_id, user_id, timestamp, {
            'fileAccessError': error_code
        })
        
        if error_code == 'NoSuchKey':
            return "Archivo no encontrado.", extraction_details
        else:
            return "Error al acceder al archivo.", extraction_details
            
    except Exception as e:
        error_msg = str(e)[:500]
        extraction_details['extractionError'] = error_msg
        
        update_processing_status(run_id, user_id, timestamp, {
            'extractionError': error_msg
        })
        
        print(f"Unexpected error: {error_msg}")
        return "Error procesando el documento.", extraction_details


def call_bedrock(model_type: str, text: str, file_names: list, run_id: str, user_id: str, timestamp: datetime) -> str:
    """Call Bedrock API with complete tracking"""
    try:
        # Update status: starting Bedrock
        update_processing_status(run_id, user_id, timestamp, {
            'bedrockStarted': True,
            'bedrockStatus': 'PROCESSING',
            'bedrockModel': BEDROCK_MODEL
        })
        
        # Sanitize and limit text
        text = sanitize_user_input(text)
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

Contenido del documento:
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
        
        # Call Bedrock
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "top_p": 0.95
        }
        
        print(f"Calling Bedrock with model: {BEDROCK_MODEL}")
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        analysis_text = response_body['content'][0]['text']
        
        # Update status: Bedrock successful
        update_processing_status(run_id, user_id, timestamp, {
            'bedrockSuccess': True,
            'bedrockStatus': 'COMPLETED',
            'bedrockResponseLength': len(analysis_text),
            'bedrockResponsePreview': analysis_text[:500]
        })
        
        print(f"Bedrock returned {len(analysis_text)} characters")
        return analysis_text
        
    except Exception as e:
        error_msg = f"Bedrock processing error: {str(e)}"
        print(error_msg)
        
        # Update status: Bedrock failed
        update_processing_status(run_id, user_id, timestamp, {
            'bedrockSuccess': False,
            'bedrockStatus': 'FAILED',
            'bedrockError': str(e)[:500]
        })
        
        return f"""ERROR EN PROCESAMIENTO

⚠️ No se pudo procesar el documento con Bedrock.

Error técnico: {str(e)[:200]}

Por favor, contacte al soporte técnico si el problema persiste.

Documentos intentados: {', '.join(file_names) if file_names else 'Sin archivos'}"""


def escape_html(text: str) -> str:
    """Escape HTML/XML special characters"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def create_docx(text: str, title: str = "INFORME ASPOR") -> bytes:
    """Create a DOCX file from text"""
    text = escape_html(text)
    
    # DOCX structure
    docx_template = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p>
                <w:pPr><w:pStyle w:val="Title"/></w:pPr>
                <w:r><w:t>{title}</w:t></w:r>
            </w:p>
            {"".join([f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.split("\\n")])}
        </w:body>
    </w:document>'''
    
    # Create ZIP structure
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add required files
        zip_file.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
        
        zip_file.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')
        
        zip_file.writestr('word/_rels/document.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>''')
        
        zip_file.writestr('word/document.xml', docx_template)
    
    return buffer.getvalue()


def generate_output_file(text: str, format: str, model: str) -> Tuple[bytes, str]:
    """Generate output file in requested format"""
    if format == 'docx':
        title = "INFORME DE CONTRAGARANTÍAS" if model == 'A' else "INFORME SOCIAL"
        content = create_docx(text, title)
        return content, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        # Default to text
        return text.encode('utf-8'), 'text/plain; charset=utf-8'


def handler(event, context):
    """Main Lambda handler with complete tracking"""
    print(f"Event: {json.dumps(event)}")
    
    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''
        }
    
    # Initialize tracking variables
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()
    user_id = None
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Extract parameters
        model = body.get('model', 'A')
        files = body.get('files', [])
        file_names = body.get('fileNames', [])
        output_format = body.get('outputFormat', 'docx')
        user_id = body.get('userId', 'web-user')
        
        # Initial validation
        if not files:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'No files provided'})
            }
        
        # Create initial DynamoDB entry with complete tracking structure
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}',
            'runId': run_id,
            'model': model,
            'files': files[:MAX_FILES_PER_RUN],
            'fileNames': file_names[:MAX_FILES_PER_RUN],
            'outputFormat': output_format,
            'status': 'PROCESSING',
            'startedAt': timestamp.isoformat(),
            'userId': user_id,
            # Processing steps tracking
            'fileUploadSuccess': True,  # Files were provided
            'textractStarted': False,
            'textractSuccess': False,
            'bedrockStarted': False,
            'bedrockSuccess': False,
            'outputGenerated': False,
            'processingComplete': False
        }
        
        table.put_item(Item=run_item)
        print(f"Created run {run_id} with initial tracking")
        
        # Extract text from all files with tracking
        all_text = ""
        all_extraction_details = []
        
        for i, s3_key in enumerate(files[:MAX_FILES_PER_RUN]):
            file_label = file_names[i] if i < len(file_names) else f"Archivo {i+1}"
            print(f"Processing file {i+1}: {s3_key}")
            
            # Update status for current file
            update_processing_status(run_id, user_id, timestamp, {
                'currentFile': file_label,
                'currentFileIndex': i + 1,
                'totalFiles': len(files[:MAX_FILES_PER_RUN])
            })
            
            text, extraction_details = extract_text_from_s3(s3_key, run_id, user_id, timestamp)
            all_extraction_details.append(extraction_details)
            
            if text and not text.startswith("Error") and not text.startswith("No se pudo"):
                all_text += f"\n--- {file_label} ---\n{text[:10000]}\n"
                print(f"Added {len(text)} characters from {file_label}")
            else:
                print(f"Failed to extract text from {file_label}: {text}")
        
        # Check if we have any text to process
        if not all_text or len(all_text.strip()) < 50:
            update_processing_status(run_id, user_id, timestamp, {
                'status': 'FAILED',
                'error': 'No text extracted from documents',
                'extractionDetails': all_extraction_details,
                'endedAt': datetime.utcnow().isoformat()
            })
            
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'error': 'No se pudo extraer texto de los documentos',
                    'runId': run_id,
                    'details': 'Verifique que los archivos sean PDFs válidos con texto'
                })
            }
        
        print(f"Total text extracted: {len(all_text)} characters")
        
        # Process with Bedrock
        analysis_result = call_bedrock(model, all_text, file_names, run_id, user_id, timestamp)
        
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
        
        update_processing_status(run_id, user_id, timestamp, {
            'outputGenerated': True,
            'outputS3Key': output_key
        })
        
        # Generate download URL
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': output_key,
                'ResponseContentDisposition': f'attachment; filename="informe_{run_id[:8]}.{output_format}"'
            },
            ExpiresIn=3600
        )
        
        # Final update with success
        update_processing_status(run_id, user_id, timestamp, {
            'status': 'COMPLETED',
            'processingComplete': True,
            'output': {
                output_format: output_key,
                'downloadUrl': download_url
            },
            'endedAt': datetime.utcnow().isoformat(),
            'extractionSummary': all_extraction_details,
            'totalProcessingTime': (datetime.utcnow() - timestamp).total_seconds()
        })
        
        print(f"Run {run_id} completed successfully")
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'runId': run_id,
                'status': 'COMPLETED',
                'downloadUrl': download_url,
                'message': 'Documento procesado exitosamente'
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Critical error: {error_msg}")
        import traceback
        print(traceback.format_exc())
        
        # Update run status to failed if we have a run_id
        if run_id and timestamp and user_id:
            try:
                update_processing_status(run_id, user_id, timestamp, {
                    'status': 'FAILED',
                    'error': error_msg[:500],
                    'endedAt': datetime.utcnow().isoformat(),
                    'processingComplete': False
                })
            except:
                pass
        
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'error': 'Error en el procesamiento',
                'details': error_msg[:200] if not os.environ.get('PRODUCTION') else None,
                'runId': run_id
            })
        }