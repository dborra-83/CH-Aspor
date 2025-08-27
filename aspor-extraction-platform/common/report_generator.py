"""
Report generation utilities for ASPOR platform
"""
import io
import zipfile
from datetime import datetime
from typing import Tuple, Optional
from .security import SecurityValidator


class ReportGenerator:
    """Unified report generation for all formats"""
    
    @staticmethod
    def generate_mock_report(model_type: str, file_names: list) -> str:
        """Generate detailed mock report - replaces duplicated code"""
        file_name = file_names[0] if file_names else "documento.pdf"
        date_str = datetime.now().strftime("%d/%m/%Y")
        
        if model_type == 'A':
            return ReportGenerator._generate_contragarantias_report(date_str, file_name)
        else:
            return ReportGenerator._generate_informe_social(date_str, file_name)
    
    @staticmethod
    def _generate_contragarantias_report(date_str: str, file_name: str) -> str:
        """Generate Model A report"""
        return f"""INFORME DE ANÁLISIS DE PODERES - ASPOR
=============================================
Fecha: {date_str}
Documento analizado: {file_name}

INFORMACIÓN SOCIETARIA
----------------------
Razón Social: EMPRESA DEMO S.A.
RUT: 76.123.456-7
Tipo: Sociedad Anónima
Domicilio: Av. Providencia 1234, Santiago, Chile

FECHAS LEGALES CRÍTICAS
-----------------------
Constitución: 15/03/2020
Escritura Pública N°: 1234
Repertorio N°: 5678
Notaría: Juan Pérez González, Santiago

Otorgamiento de Poderes: 20/01/2024
Escritura Pública N°: 4567
Repertorio N°: 8901
Notaría: María Silva Rojas, Santiago

VALIDACIÓN PARA CONTRAGARANTÍAS
-------------------------------
APODERADOS CLASE A:
1. Juan Carlos Pérez González
   RUT: 12.345.678-9
   Facultades:
   ✓ Suscribir pagarés
   ✓ Otorgar mandatos
   ✓ Contratar seguros
   
2. María Isabel González Silva
   RUT: 10.987.654-3
   Facultades:
   ✓ Suscribir pagarés
   ✓ Otorgar mandatos
   ✓ Contratar seguros

FORMA DE ACTUACIÓN:
- Contragarantías simples: Un apoderado Clase A actuando individualmente
- Contragarantías avaladas: Dos apoderados Clase A actuando conjuntamente

CONCLUSIÓN
----------
Los apoderados identificados PUEDEN firmar contragarantías simples para ASPOR
actuando individualmente, y contragarantías avaladas actuando en conjunto.

OBSERVACIONES
-------------
- Poderes vigentes al {date_str}
- No se detectaron limitaciones estatutarias
- Facultades suficientes para el proceso ASPOR

---
Informe generado automáticamente
Sistema de Análisis ASPOR v1.1"""
    
    @staticmethod
    def _generate_informe_social(date_str: str, file_name: str) -> str:
        """Generate Model B report"""
        return f"""INFORME SOCIAL
================
Santiago, {date_str}

CLIENTE: EMPRESA DEMO S.A.
R.U.T. 76.123.456-7

1. ANTECEDENTES DEL CLIENTE
---------------------------
R.U.T. cliente: 76.123.456-7
Razón Social: EMPRESA DEMO S.A.
Nombre Fantasía: DEMO
Calidad Jurídica: Sociedad Anónima

2. OBJETO SOCIAL
---------------
La sociedad tiene por objeto:
a) El desarrollo de actividades comerciales e industriales en general;
b) La importación, exportación, distribución y comercialización de toda clase de bienes;
c) La prestación de servicios de asesoría y consultoría;
d) La realización de inversiones en toda clase de bienes muebles e inmuebles;
e) En general, la realización de cualquier actividad relacionada directa o
   indirectamente con los objetos anteriores.

3. CAPITAL SOCIAL
----------------
Capital Total: $100.000.000 (cien millones de pesos)
Capital Suscrito: $100.000.000
Capital Pagado: $100.000.000
División: 10.000 acciones ordinarias, nominativas, de igual valor

4. SOCIOS O ACCIONISTAS Y PARTICIPACIÓN
---------------------------------------
R.U.T.          Nombre                      % Capital    % Utilidades
12.345.678-9    Juan Pérez González         40%          40%
10.987.654-3    María González Silva        35%          35%
11.222.333-4    Pedro Rodríguez López       25%          25%

5. ADMINISTRACIÓN
----------------
Tipo: Directorio
Número de miembros: 5 directores titulares
Duración: 3 años
Quórum de sesión: Mayoría absoluta
Quórum de acuerdos: Mayoría de los presentes
Decisiones unánimes: Modificación de estatutos

6. DIRECTORIO
------------
Apellido Paterno    Apellido Materno    Nombres              R.U.T.
Pérez              González            Juan Carlos          12.345.678-9
González           Silva               María Isabel         10.987.654-3
Rodríguez          López               Pedro Antonio        11.222.333-4
Martínez           Díaz                Ana Luisa           14.555.666-7
Sánchez            Vera                Roberto José        15.666.777-8

7. VIGENCIA
----------
Duración: Indefinida

8. DOMICILIO
-----------
Domicilio Legal: Santiago, Región Metropolitana
Dirección: Av. Providencia 1234, Oficina 567, Providencia
Sucursales: No registra

9. ANTECEDENTES LEGALES
-----------------------
Constitución:
- Fecha escritura: 15/03/2020
- Repertorio N°: 1234
- Notaría: Juan Pérez González, Santiago
- Inscripción Registro Comercio: Fs. 5678 N° 2345 del 20/03/2020
- Publicación Diario Oficial: 25/03/2020

Modificaciones: La sociedad no ha sufrido modificaciones

10. APODERADOS
-------------
Apellido Paterno    Apellido Materno    Nombres              R.U.T.
Pérez              González            Juan Carlos          12.345.678-9
González           Silva               María Isabel         10.987.654-3

11. GRUPOS DE APODERADOS Y FACULTADES
-------------------------------------
Grupo 1: Un apoderado actuando individualmente
Personería: Escritura pública Rep. N° 4567 del 20/01/2024, Notaría María Silva R.
Facultades:
1. Representar a la sociedad ante toda clase de autoridades
2. Celebrar contratos hasta 1000 UF
3. Abrir y cerrar cuentas corrientes
4. Girar y endosar cheques
5. Contratar personal

---
Informe emitido para fines informativos
Documento analizado: {file_name}"""
    
    @staticmethod
    def create_docx(text: str, title: str = "INFORME ASPOR") -> bytes:
        """Create a valid DOCX file"""
        # Escape XML special characters
        text = SecurityValidator.escape_html(text)
        
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
                <w:t>{SecurityValidator.escape_html(title)}</w:t>
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
    
    @staticmethod
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
    
    @staticmethod
    def generate_output_file(text: str, format_type: str, model: str) -> Tuple[bytes, str]:
        """Generate output file in requested format"""
        title = "INFORME DE CONTRAGARANTÍAS" if model == 'A' else "INFORME SOCIAL"
        
        if format_type == 'docx':
            content = ReportGenerator.create_docx(text, title)
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif format_type == 'pdf':
            content = ReportGenerator.create_pdf(text, title)
            content_type = 'application/pdf'
        else:  # txt
            content = text.encode('utf-8')
            content_type = 'text/plain; charset=utf-8'
        
        return content, content_type