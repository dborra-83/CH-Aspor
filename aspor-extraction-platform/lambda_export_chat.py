"""
Lambda handler for exporting chat analysis to DOCX/PDF
"""
import json
import boto3
import os
import io
import zipfile
from datetime import datetime
import uuid

s3_client = boto3.client('s3')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')


def create_formatted_docx(analysis_text: str, model_type: str) -> bytes:
    """Create a properly formatted DOCX file from analysis text"""
    
    # Escape XML special characters
    def escape_xml(text):
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
    
    # Parse the analysis text into structured sections
    lines = analysis_text.split('\n')
    paragraphs_xml = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            paragraphs_xml += '<w:p/>'
            continue
            
        # Detect headers (lines with === or ---)
        is_main_header = '===' in line
        is_sub_header = '---' in line or line.isupper()
        
        # Skip separator lines
        if line.replace('=', '').replace('-', '').strip() == '':
            continue
        
        # Format based on line type
        if is_main_header or (line.isupper() and len(line) > 5):
            # Main headers
            paragraphs_xml += f'''<w:p>
                <w:pPr>
                    <w:pStyle w:val="Heading1"/>
                    <w:spacing w:before="240" w:after="120"/>
                </w:pPr>
                <w:r>
                    <w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="1F2937"/></w:rPr>
                    <w:t>{escape_xml(line)}</w:t>
                </w:r>
            </w:p>'''
        elif is_sub_header or line.endswith(':'):
            # Sub headers
            paragraphs_xml += f'''<w:p>
                <w:pPr>
                    <w:pStyle w:val="Heading2"/>
                    <w:spacing w:before="120" w:after="60"/>
                </w:pPr>
                <w:r>
                    <w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="374151"/></w:rPr>
                    <w:t>{escape_xml(line)}</w:t>
                </w:r>
            </w:p>'''
        elif line.startswith('•') or line.startswith('-'):
            # Bullet points
            clean_line = line.replace('•', '').replace('-', '', 1).strip()
            paragraphs_xml += f'''<w:p>
                <w:pPr>
                    <w:numPr>
                        <w:ilvl w:val="0"/>
                        <w:numId w:val="1"/>
                    </w:numPr>
                    <w:spacing w:after="60"/>
                </w:pPr>
                <w:r>
                    <w:t>{escape_xml(clean_line)}</w:t>
                </w:r>
            </w:p>'''
        elif line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
            # Numbered items
            paragraphs_xml += f'''<w:p>
                <w:pPr>
                    <w:spacing w:before="60" w:after="60"/>
                </w:pPr>
                <w:r>
                    <w:rPr><w:b/></w:rPr>
                    <w:t>{escape_xml(line)}</w:t>
                </w:r>
            </w:p>'''
        else:
            # Normal paragraphs
            paragraphs_xml += f'''<w:p>
                <w:pPr>
                    <w:spacing w:after="120"/>
                </w:pPr>
                <w:r>
                    <w:t>{escape_xml(line)}</w:t>
                </w:r>
            </w:p>'''
    
    # DOCX structure with enhanced styling
    title = "INFORME DE CONTRAGARANTÍAS ASPOR" if model_type == 'A' else "INFORME SOCIAL ASPOR"
    
    docx_files = {
        '[Content_Types].xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
    <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>''',
        
        '_rels/.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''',
        
        'word/_rels/document.xml.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>''',
        
        'word/numbering.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:abstractNum w:abstractNumId="0">
        <w:lvl w:ilvl="0">
            <w:start w:val="1"/>
            <w:numFmt w:val="bullet"/>
            <w:lvlText w:val="•"/>
            <w:lvlJc w:val="left"/>
            <w:pPr>
                <w:ind w:left="720" w:hanging="360"/>
            </w:pPr>
        </w:lvl>
    </w:abstractNum>
    <w:num w:numId="1">
        <w:abstractNumId w:val="0"/>
    </w:num>
</w:numbering>''',
        
        'word/styles.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:style w:type="paragraph" w:styleId="Normal" w:default="1">
        <w:name w:val="Normal"/>
        <w:rPr>
            <w:sz w:val="24"/>
            <w:szCs w:val="24"/>
            <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        </w:rPr>
        <w:pPr>
            <w:spacing w:line="276" w:lineRule="auto"/>
        </w:pPr>
    </w:style>
    <w:style w:type="paragraph" w:styleId="Heading1">
        <w:name w:val="Heading 1"/>
        <w:basedOn w:val="Normal"/>
        <w:pPr>
            <w:keepNext/>
            <w:spacing w:before="240" w:after="120"/>
        </w:pPr>
        <w:rPr>
            <w:b/>
            <w:sz w:val="36"/>
            <w:color w:val="1F2937"/>
        </w:rPr>
    </w:style>
    <w:style w:type="paragraph" w:styleId="Heading2">
        <w:name w:val="Heading 2"/>
        <w:basedOn w:val="Normal"/>
        <w:pPr>
            <w:keepNext/>
            <w:spacing w:before="120" w:after="60"/>
        </w:pPr>
        <w:rPr>
            <w:b/>
            <w:sz w:val="28"/>
            <w:color w:val="374151"/>
        </w:rPr>
    </w:style>
</w:styles>''',
        
        'word/document.xml': f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <!-- Title Page -->
        <w:p>
            <w:pPr>
                <w:jc w:val="center"/>
                <w:spacing w:before="480" w:after="240"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:b/>
                    <w:sz w:val="48"/>
                    <w:color w:val="764BA2"/>
                </w:rPr>
                <w:t>{escape_xml(title)}</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:pPr>
                <w:jc w:val="center"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:sz w:val="24"/>
                    <w:color w:val="6B7280"/>
                </w:rPr>
                <w:t>Generado el {datetime.now().strftime("%d de %B de %Y")}</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:pPr>
                <w:pageBreakBefore/>
            </w:pPr>
        </w:p>
        
        <!-- Content -->
        {paragraphs_xml}
        
        <!-- Footer -->
        <w:p>
            <w:pPr>
                <w:spacing w:before="480"/>
                <w:jc w:val="center"/>
                <w:bdr>
                    <w:top w:val="single" w:sz="6" w:space="1" w:color="D1D5DB"/>
                </w:bdr>
            </w:pPr>
        </w:p>
        <w:p>
            <w:pPr>
                <w:jc w:val="center"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:sz w:val="20"/>
                    <w:color w:val="9CA3AF"/>
                    <w:i/>
                </w:rPr>
                <w:t>Documento generado automáticamente por el Sistema ASPOR</w:t>
            </w:r>
        </w:p>
        
        <w:sectPr>
            <w:pgSz w:w="11906" w:h="16838"/>
            <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/>
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


def create_formatted_pdf(analysis_text: str, model_type: str) -> bytes:
    """Create a basic PDF from analysis text"""
    title = "INFORME DE CONTRAGARANTÍAS ASPOR" if model_type == 'A' else "INFORME SOCIAL ASPOR"
    
    # Clean text for PDF
    def clean_for_pdf(text):
        return text.replace('(', '\\(').replace(')', '\\)').replace('\\', '\\\\')
    
    lines = analysis_text.split('\n')
    
    # Create PDF content stream
    content_lines = []
    y_position = 750
    
    # Add title
    content_lines.append('BT')
    content_lines.append('/F1 18 Tf')
    content_lines.append(f'50 {y_position} Td')
    content_lines.append(f'({clean_for_pdf(title)}) Tj')
    content_lines.append('ET')
    y_position -= 40
    
    # Add date
    content_lines.append('BT')
    content_lines.append('/F1 10 Tf')
    content_lines.append(f'50 {y_position} Td')
    content_lines.append(f'(Generado el {datetime.now().strftime("%d/%m/%Y")}) Tj')
    content_lines.append('ET')
    y_position -= 30
    
    # Add content
    for line in lines[:60]:  # Limit to fit on pages
        if line.strip() and y_position > 50:
            # Adjust font size for headers
            if line.isupper() and len(line) > 5:
                font_size = 12
                y_position -= 5
            else:
                font_size = 10
                
            line_clean = clean_for_pdf(line[:90])  # Limit line length
            content_lines.append('BT')
            content_lines.append(f'/F1 {font_size} Tf')
            content_lines.append(f'50 {y_position} Td')
            content_lines.append(f'({line_clean}) Tj')
            content_lines.append('ET')
            y_position -= 15
            
            if y_position < 50:
                break
    
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


def handler(event, context):
    """Export chat analysis to DOCX or PDF"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        analysis_text = body.get('analysis', '')
        format_type = body.get('format', 'docx').lower()
        model_type = body.get('model', 'A')
        session_id = body.get('sessionId', str(uuid.uuid4()))
        
        if not analysis_text:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'No analysis text provided'})
            }
        
        # Generate the document
        if format_type == 'pdf':
            document_content = create_formatted_pdf(analysis_text, model_type)
            content_type = 'application/pdf'
            extension = 'pdf'
        else:
            document_content = create_formatted_docx(analysis_text, model_type)
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            extension = 'docx'
        
        # Save to S3
        output_key = f'exports/{session_id}/report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{extension}'
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=document_content,
            ContentType=content_type,
            ServerSideEncryption='AES256',
            Metadata={
                'session_id': session_id,
                'model': model_type,
                'format': format_type
            }
        )
        
        # Generate download URL
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': output_key,
                'ResponseContentDisposition': f'attachment; filename="informe_aspor_{datetime.now().strftime("%Y%m%d")}.{extension}"'
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
                'filename': f'informe_aspor_{datetime.now().strftime("%Y%m%d")}.{extension}'
            })
        }
        
    except Exception as e:
        print(f"Export error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Error generating document'})
        }