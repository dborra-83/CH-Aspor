import json
import boto3
import os
import uuid
from datetime import datetime
import base64
import io
import zipfile

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
ssm = boto3.client('ssm', region_name='us-east-1')
textract = boto3.client('textract', region_name='us-east-1')

# Environment variables
table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

def get_prompt_from_ssm(model):
    """Get prompt from S3 bucket"""
    try:
        # Try S3 first for full prompts
        if model == 'A':
            s3_key = 'prompts/contragarantias.txt'
        else:
            s3_key = 'prompts/informes-sociales.txt'
        
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        prompt = response['Body'].read().decode('utf-8')
        print(f"Loaded prompt from S3: {s3_key}, size: {len(prompt)} chars")
        return prompt
        
    except Exception as e:
        print(f"Error getting prompt from S3: {str(e)}")
        
        # Fallback to SSM
        try:
            if model == 'A':
                param_name = '/aspor/prompts/agent-a-contragarantias'
            else:
                param_name = '/aspor/prompts/agent-b-informes'
            
            response = ssm.get_parameter(Name=param_name, WithDecryption=True)
            return response['Parameter']['Value']
        except Exception as e2:
            print(f"Error getting prompt from SSM: {str(e2)}")
            # Return default prompts if both fail
            if model == 'A':
                return get_default_prompt_a()
            else:
                return get_default_prompt_b()

def get_default_prompt_a():
    """Default prompt for Model A - Contragarantías"""
    return """Eres un asistente legal experto en análisis de documentos societarios y validación de facultades para otorgar contragarantías. Tu tarea es analizar los documentos proporcionados y determinar si los representantes tienen las facultades necesarias.

ANALIZA Y VALIDA:
1. Identificación de la sociedad
2. Representantes legales y sus facultades
3. Limitaciones o restricciones para otorgar garantías
4. Vigencia de los poderes
5. Cumplimiento de requisitos legales

GENERA UN INFORME ESTRUCTURADO que incluya:

DATOS DE LA SOCIEDAD:
- Razón Social
- RUT
- Tipo de sociedad
- Domicilio legal

REPRESENTANTES AUTORIZADOS:
- Nombre completo
- RUT
- Cargo
- Facultades específicas

VALIDACIÓN DE FACULTADES:
- ¿Pueden otorgar contragarantías? (SÍ/NO)
- Fundamento legal
- Limitaciones detectadas
- Requisitos adicionales

ALERTAS Y OBSERVACIONES:
- Restricciones importantes
- Documentos faltantes
- Recomendaciones

CONCLUSIÓN:
- Resumen ejecutivo de la validación"""

def get_default_prompt_b():
    """Default prompt for Model B - Informes Sociales"""
    return """Eres un asistente experto en análisis de documentos corporativos y generación de informes sociales profesionales. Tu tarea es analizar los documentos proporcionados y generar un informe social completo y detallado.

GENERA UN INFORME SOCIAL PROFESIONAL con la siguiente estructura:

1. IDENTIFICACIÓN DE LA SOCIEDAD
- Razón Social
- Nombre de Fantasía
- RUT
- Tipo societario
- Fecha de constitución

2. DATOS DE CONTACTO
- Domicilio legal
- Dirección comercial
- Teléfono
- Email
- Sitio web

3. OBJETO SOCIAL
- Actividad principal
- Actividades secundarias
- Código de actividad económica

4. CAPITAL Y PARTICIPACIÓN
- Capital social
- Capital pagado
- Distribución de participación

5. ADMINISTRACIÓN
- Estructura administrativa
- Órganos de gobierno
- Facultades de administración

6. REPRESENTANTES LEGALES
(Tabla con: Apellido Paterno, Apellido Materno, Nombres, RUT)

7. VIGENCIA
- Duración de la sociedad
- Fecha de término (si aplica)

8. DOMICILIO
- Domicilio legal
- Sucursales

9. ANTECEDENTES LEGALES
- Constitución
- Modificaciones
- Inscripciones

10. APODERADOS
(Tabla con: Apellido Paterno, Apellido Materno, Nombres, RUT)

11. GRUPOS DE APODERADOS Y FACULTADES
- Grupos definidos
- Facultades por grupo
- Limitaciones

Formato: Profesional, claro y estructurado"""

def extract_text_from_file(bucket, key):
    """Extract text from uploaded file (PDF or DOCX)"""
    try:
        print(f"Extracting text from: {bucket}/{key}")
        
        # Get file from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = response['Body'].read()
        
        # Determine file type
        file_extension = key.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            print(f"Processing PDF file, size: {len(file_content)} bytes")
            
            # For large PDFs, we need to handle them differently
            if len(file_content) > 5 * 1024 * 1024:  # 5MB
                return "Archivo PDF muy grande. Por favor use un archivo más pequeño."
            
            try:
                # Use Textract for PDF
                response = textract.detect_document_text(
                    Document={'Bytes': file_content}
                )
                
                text = ""
                for block in response.get('Blocks', []):
                    if block.get('BlockType') == 'LINE':
                        text += block.get('Text', '') + '\n'
                
                print(f"Extracted {len(text)} characters from PDF")
                return text if text else "No se pudo extraer texto del PDF"
            except Exception as e:
                print(f"Textract error: {str(e)}")
                return f"Error al procesar PDF: {str(e)}"
            
        elif file_extension in ['docx', 'doc']:
            # Extract text from DOCX
            try:
                # DOCX files are ZIP archives
                zip_buffer = io.BytesIO(file_content)
                with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                    # Read document.xml
                    if 'word/document.xml' in zip_file.namelist():
                        doc_xml = zip_file.read('word/document.xml').decode('utf-8')
                        # Simple text extraction from XML
                        import re
                        text = re.sub(r'<[^>]+>', ' ', doc_xml)
                        text = re.sub(r'\s+', ' ', text)
                        return text
            except:
                pass
        
        # Fallback: treat as plain text
        return file_content.decode('utf-8', errors='ignore')
        
    except Exception as e:
        print(f"Error extracting text: {str(e)}")
        return f"Error al procesar archivo: {key}"

def call_bedrock_claude(prompt, extracted_text):
    """Call Bedrock Claude for analysis"""
    try:
        # Combine prompt with extracted text (limit text to avoid token limits)
        extracted_text = extracted_text[:15000]  # Limit to ~15k chars
        full_prompt = f"{prompt}\n\nDOCUMENTO A ANALIZAR:\n{extracted_text}"
        
        # Call Bedrock with correct model ID
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                "temperature": 0.1
            })
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        analysis = response_body['content'][0]['text']
        
        return analysis
        
    except Exception as e:
        print(f"Error calling Bedrock: {str(e)}")
        # Return a more user-friendly error message
        if "ValidationException" in str(e):
            return "Error: Modelo de IA no disponible. Por favor contacte al administrador."
        elif "ThrottlingException" in str(e):
            return "Error: Límite de llamadas excedido. Por favor intente más tarde."
        else:
            return f"Error en el análisis. Por favor intente nuevamente."

def create_proper_docx(text, title="Reporte ASPOR"):
    """Create a proper DOCX file with UTF-8 support"""
    
    # Ensure text is properly encoded
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    if isinstance(title, bytes):
        title = title.decode('utf-8')
    
    # Create the required DOCX structure
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    
    # Process text for XML - escape special characters but keep Unicode
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
    title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
    
    # Split text into paragraphs and create proper DOCX XML
    paragraphs = text.split('\n')
    para_xml = ""
    
    for para in paragraphs:
        if para.strip():
            # Check if it's a title (all caps or starts with number)
            if para.isupper() or (para[:2].strip() and para[0].isdigit()):
                # Bold title
                para_xml += f"""<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{para}</w:t></w:r></w:p>"""
            else:
                # Regular paragraph
                para_xml += f"""<w:p><w:r><w:t xml:space="preserve">{para}</w:t></w:r></w:p>"""
    
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:pPr><w:jc w:val="center"/></w:pPr>
            <w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t xml:space="preserve">{title}</w:t></w:r>
        </w:p>
        <w:p><w:r><w:t></w:t></w:r></w:p>
        {para_xml}
    </w:body>
</w:document>"""
    
    # Create DOCX as ZIP with UTF-8 encoding
    docx_buffer = io.BytesIO()
    with zipfile.ZipFile(docx_buffer, 'w', zipfile.ZIP_DEFLATED) as docx:
        docx.writestr('[Content_Types].xml', content_types.encode('utf-8'))
        docx.writestr('_rels/.rels', rels.encode('utf-8'))
        docx.writestr('word/document.xml', document.encode('utf-8'))
    
    return docx_buffer.getvalue()

def create_proper_pdf(text, title="Reporte ASPOR"):
    """Create a PDF file with UTF-8 text support using ReportLab approach"""
    
    # Ensure text is properly encoded
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    if isinstance(title, bytes):
        title = title.decode('utf-8')
    
    # For a simple PDF that handles Spanish characters, we'll create a minimal structure
    # Convert special characters to their escape sequences
    def encode_pdf_string(s):
        # Replace special characters with octal codes for PDF
        replacements = {
            'á': '\\341', 'é': '\\351', 'í': '\\355', 'ó': '\\363', 'ú': '\\372',
            'Á': '\\301', 'É': '\\311', 'Í': '\\315', 'Ó': '\\323', 'Ú': '\\332',
            'ñ': '\\361', 'Ñ': '\\321', '¿': '\\277', '¡': '\\241',
            '(': '\\(', ')': '\\)', '\\': '\\\\', '\n': ' '
        }
        for char, replacement in replacements.items():
            s = s.replace(char, replacement)
        return s
    
    # Clean title and text
    title_encoded = encode_pdf_string(title)
    
    # Split text into lines and pages
    lines = text.split('\n')
    pages = []
    current_page = []
    lines_per_page = 50
    
    for line in lines:
        if len(current_page) >= lines_per_page:
            pages.append(current_page)
            current_page = []
        if line.strip():
            current_page.append(encode_pdf_string(line[:100]))  # Limit line length
    
    if current_page:
        pages.append(current_page)
    
    # If no pages, create at least one
    if not pages:
        pages = [["Documento vacío"]]
    
    # Build PDF with first page only (simplified)
    pdf_lines = []
    y_position = 750
    
    # Add title
    pdf_lines.append(f"BT /F1 14 Tf 50 {y_position} Td ({title_encoded}) Tj ET")
    y_position -= 30
    
    # Add content from first page
    for line in pages[0]:
        if y_position < 50:
            break
        pdf_lines.append(f"BT /F1 10 Tf 50 {y_position} Td ({line}) Tj ET")
        y_position -= 15
    
    content_stream = '\n'.join(pdf_lines)
    
    # Build PDF structure with Latin-1 encoding support
    pdf = f"""%PDF-1.4
%âãÏÓ
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> >> >>
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
0000000015 00000 n 
0000000074 00000 n 
0000000131 00000 n 
0000000329 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
{329 + len(content_stream) + 25}
%%EOF"""
    
    # Return as bytes with proper encoding
    return pdf.encode('latin-1', errors='replace')

def handler(event, context):
    """Main Lambda handler for document processing"""
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        model = body.get('model')
        files = body.get('files', [])
        file_names = body.get('fileNames', [])
        output_format = body.get('outputFormat', 'docx')
        user_id = body.get('userId', 'default-user')
        
        print(f"Processing request: model={model}, files={files}, format={output_format}")
        
        # Generate run ID
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Create DynamoDB entry
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp}#{run_id}',
            'runId': run_id,
            'model': model,
            'modelName': 'Contragarantías/ASPOR' if model == 'A' else 'Informes Sociales',
            'files': files,
            'fileNames': file_names,
            'displayName': ', '.join(file_names[:2]) + (f' (+{len(file_names)-2})' if len(file_names) > 2 else ''),
            'status': 'PROCESSING',
            'outputFormat': output_format,
            'startedAt': timestamp,
            'userId': user_id
        }
        
        table.put_item(Item=run_item)
        
        # Get prompt from SSM
        prompt = get_prompt_from_ssm(model)
        
        # Extract text from all files
        all_text = ""
        for i, s3_key in enumerate(files):
            file_name = file_names[i] if i < len(file_names) else f"documento_{i+1}"
            all_text += f"\n\n--- DOCUMENTO: {file_name} ---\n\n"
            all_text += extract_text_from_file(bucket_name, s3_key)
        
        # Call Bedrock for analysis
        analysis = call_bedrock_claude(prompt, all_text)
        
        # Generate title based on model
        if model == 'A':
            report_title = "INFORME DE VALIDACIÓN DE FACULTADES - CONTRAGARANTÍAS"
        else:
            report_title = "INFORME SOCIAL CORPORATIVO"
        
        # Generate output files
        if output_format == 'docx':
            output_content = create_proper_docx(analysis, report_title)
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            output_content = create_proper_pdf(analysis, report_title)
            content_type = 'application/pdf'
        
        # Save output to S3
        output_key = f'outputs/{run_id}/report.{output_format}'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=output_content,
            ContentType=content_type
        )
        
        # Also save the analysis text for preview
        analysis_key = f'outputs/{run_id}/analysis.txt'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=analysis_key,
            Body=analysis.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Generate download URL
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': output_key,
                'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{output_format}"'
            },
            ExpiresIn=3600
        )
        
        # Update DynamoDB with completion
        run_item['status'] = 'COMPLETED'
        run_item['completedAt'] = datetime.utcnow().isoformat()
        run_item['output'] = {
            's3_key': output_key,
            'downloadUrl': download_url,
            'analysis_content': analysis[:1000]  # Store first 1000 chars for preview
        }
        
        table.put_item(Item=run_item)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'runId': run_id,
                'status': 'COMPLETED',
                'output': {
                    'downloadUrl': download_url
                }
            })
        }
        
    except Exception as e:
        print(f"Error in handler: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Update DynamoDB with error
        if 'run_item' in locals():
            run_item['status'] = 'FAILED'
            run_item['error'] = str(e)
            run_item['completedAt'] = datetime.utcnow().isoformat()
            table.put_item(Item=run_item)
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Error processing documents',
                'details': str(e)
            })
        }