import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

def handler(event, context):
    """Handle download requests for specific formats"""
    try:
        run_id = event.get('pathParameters', {}).get('runId')
        format_type = event.get('pathParameters', {}).get('format', 'docx')
        user_id = event.get('queryStringParameters', {}).get('userId', 'default-user')
        
        print(f"Download request: run={run_id}, format={format_type}, user={user_id}")
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Run ID is required'})
            }
        
        # Query for the run
        response = table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#')
        )
        
        # Find matching run
        matching_run = None
        for item in response.get('Items', []):
            if item.get('runId') == run_id:
                matching_run = item
                break
        
        if not matching_run:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Run not found'})
            }
        
        # Check if file exists for requested format
        s3_key = f'outputs/{run_id}/report.{format_type}'
        
        try:
            # Check if file exists
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            
            # Generate presigned URL
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if format_type == 'docx' else 'application/pdf'
            
            download_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_key,
                    'ResponseContentType': content_type,
                    'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                },
                ExpiresIn=3600
            )
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'downloadUrl': download_url,
                    'format': format_type,
                    'filename': f'reporte_{run_id[:8]}.{format_type}'
                })
            }
            
        except s3_client.exceptions.NoSuchKey:
            # File doesn't exist for this format, try to generate it
            
            # Get the analysis text
            try:
                analysis_key = f'outputs/{run_id}/analysis.txt'
                response = s3_client.get_object(Bucket=bucket_name, Key=analysis_key)
                analysis_text = response['Body'].read().decode('utf-8')
            except:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': f'No se puede generar el archivo {format_type.upper()}'})
                }
            
            # Generate the file in the requested format
            if format_type == 'docx':
                file_content = generate_docx(analysis_text, matching_run.get('model'))
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            else:
                file_content = generate_pdf(analysis_text, matching_run.get('model'))
                content_type = 'application/pdf'
            
            # Save to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
            
            # Generate download URL
            download_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_key,
                    'ResponseContentType': content_type,
                    'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                },
                ExpiresIn=3600
            )
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'downloadUrl': download_url,
                    'format': format_type,
                    'filename': f'reporte_{run_id[:8]}.{format_type}',
                    'generated': True
                })
            }
            
    except Exception as e:
        print(f"Error in download handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Error interno del servidor'})
        }

def generate_docx(text, model):
    """Generate a DOCX file with proper UTF-8 encoding"""
    import io
    import zipfile
    
    # Ensure text is UTF-8
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    
    # Escape special XML characters properly
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
    
    # Create minimal DOCX structure
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''
    
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
    
    # Create document with paragraphs
    paragraphs = text.split('\n')
    para_xml = ""
    
    for para in paragraphs:
        if para.strip():
            para_xml += f'<w:p><w:r><w:t xml:space="preserve">{para}</w:t></w:r></w:p>'
    
    title = "INFORME DE CONTRAGARANTÍAS" if model == 'A' else "INFORME SOCIAL CORPORATIVO"
    
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t xml:space="preserve">{title}</w:t></w:r></w:p>
        <w:p><w:r><w:t></w:t></w:r></w:p>
        {para_xml}
    </w:body>
</w:document>'''
    
    # Create ZIP file with UTF-8 encoding
    docx_buffer = io.BytesIO()
    with zipfile.ZipFile(docx_buffer, 'w', zipfile.ZIP_DEFLATED) as docx:
        docx.writestr('[Content_Types].xml', content_types.encode('utf-8'))
        docx.writestr('_rels/.rels', rels.encode('utf-8'))
        docx.writestr('word/document.xml', document.encode('utf-8'))
    
    return docx_buffer.getvalue()

def generate_pdf(text, model):
    """Generate a simple PDF file"""
    
    title = "INFORME DE CONTRAGARANTÍAS" if model == 'A' else "INFORME SOCIAL CORPORATIVO"
    
    # Create basic PDF structure
    lines = text.split('\n')
    content_stream = []
    y_position = 750
    
    # Add title
    content_stream.append(f"BT /F1 14 Tf 50 {y_position} Td ({title}) Tj ET")
    y_position -= 30
    
    # Add content (limited to avoid complexity)
    for line in lines[:60]:
        if line.strip() and y_position > 50:
            # Escape parentheses
            line = line[:80].replace('(', '\\(').replace(')', '\\)')
            content_stream.append(f"BT /F1 10 Tf 50 {y_position} Td ({line}) Tj ET")
            y_position -= 15
    
    stream = '\n'.join(content_stream)
    
    pdf = f"""%PDF-1.4
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
<< /Length {len(stream)} >>
stream
{stream}
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
{274 + len(stream) + 25}
%%EOF"""
    
    return pdf.encode('latin-1', errors='ignore')