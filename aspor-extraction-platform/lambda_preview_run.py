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
    """Get preview content for a specific run"""
    try:
        run_id = event.get('pathParameters', {}).get('runId')
        user_id = event.get('queryStringParameters', {}).get('userId', 'default-user')
        
        print(f"Getting preview for run: {run_id} for user: {user_id}")
        
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
        
        # Find the matching runId
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
        
        run = matching_run
        
        # Get the analysis content from S3 if available
        preview_content = None
        if run.get('status') == 'COMPLETED':
            # First try to get from output field
            analysis_content = run.get('output', {}).get('analysis_content', '')
            
            if not analysis_content:
                # Try to read from S3
                try:
                    s3_key = f'outputs/{run_id}/analysis.txt'
                    print(f"Reading analysis from S3: {s3_key}")
                    response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                    analysis_content = response['Body'].read().decode('utf-8')
                except Exception as e:
                    print(f"Error reading from S3: {str(e)}")
                    analysis_content = ""
            
            if analysis_content:
                preview_content = format_as_html(analysis_content, run.get('model'), run.get('fileNames', []))
            else:
                preview_content = "<p>El contenido del análisis no está disponible. Por favor descargue el reporte.</p>"
        else:
            preview_content = "<p>El procesamiento aún no ha finalizado.</p>"
        
        # Generate download URLs
        download_urls = {}
        if run.get('status') == 'COMPLETED':
            for format_type in ['docx', 'pdf']:
                s3_key = f'outputs/{run_id}/report.{format_type}'
                try:
                    # Check if file exists
                    s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                    # Generate presigned URL
                    download_urls[format_type] = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': bucket_name,
                            'Key': s3_key,
                            'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                        },
                        ExpiresIn=3600
                    )
                except:
                    pass
        
        response_data = {
            'runId': run.get('runId'),
            'model': run.get('model'),
            'modelName': run.get('modelName', 'Modelo ' + run.get('model', 'A')),
            'status': run.get('status'),
            'startedAt': run.get('startedAt'),
            'completedAt': run.get('completedAt'),
            'fileNames': run.get('fileNames', []),
            'previewContent': preview_content,
            'downloadUrls': download_urls
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data, default=str)
        }
        
    except Exception as e:
        print(f"Error getting preview: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }

def format_as_html(content, model, file_names):
    """Format the analysis content as HTML"""
    
    # Get model name
    model_name = "Contragarantías/ASPOR" if model == 'A' else "Informes Sociales"
    
    # Create HTML structure
    html = f"""
    <div class="preview-header">
        <h2>{model_name}</h2>
        <p class="files-info">Archivos procesados: {', '.join(file_names)}</p>
    </div>
    <div class="preview-body">
    """
    
    # Process content based on model type
    if model == 'A':
        # Model A: Contragarantías
        sections = content.split('\n\n')
        for section in sections:
            if section.strip():
                if section.startswith('VALIDACIÓN'):
                    html += f'<div class="section validation">'
                    html += f'<h3>{section.split(":")[0]}</h3>'
                    html += f'<p>{":".join(section.split(":")[1:])}</p>'
                    html += '</div>'
                elif section.startswith('ALERTA') or section.startswith('ADVERTENCIA'):
                    html += f'<div class="section alert">'
                    html += f'<h3 class="alert-title">{section.split(":")[0]}</h3>'
                    html += f'<p class="alert-content">{":".join(section.split(":")[1:])}</p>'
                    html += '</div>'
                elif ':' in section:
                    parts = section.split(':', 1)
                    html += f'<div class="section">'
                    html += f'<h3>{parts[0]}</h3>'
                    if len(parts) > 1:
                        # Check if it's a list
                        if '\n-' in parts[1] or '\n•' in parts[1]:
                            html += '<ul>'
                            for item in parts[1].split('\n'):
                                item = item.strip()
                                if item.startswith('-') or item.startswith('•'):
                                    html += f'<li>{item[1:].strip()}</li>'
                            html += '</ul>'
                        else:
                            html += f'<p>{parts[1].strip()}</p>'
                    html += '</div>'
                else:
                    html += f'<div class="section"><p>{section}</p></div>'
    else:
        # Model B: Informes Sociales
        sections = content.split('\n\n')
        for section in sections:
            if section.strip():
                if section.upper() == section and len(section) < 100:
                    # It's a title
                    html += f'<h3 class="report-title">{section}</h3>'
                elif ':' in section and section.index(':') < 50:
                    parts = section.split(':', 1)
                    html += f'<div class="section">'
                    html += f'<h4>{parts[0]}</h4>'
                    if len(parts) > 1:
                        # Check if it's a list
                        if '\n-' in parts[1] or '\n•' in parts[1] or '\n1.' in parts[1]:
                            html += '<ul>'
                            for item in parts[1].split('\n'):
                                item = item.strip()
                                if item and (item[0].isdigit() or item.startswith('-') or item.startswith('•')):
                                    # Remove number or bullet
                                    clean_item = item.lstrip('0123456789.-• ')
                                    html += f'<li>{clean_item}</li>'
                            html += '</ul>'
                        else:
                            html += f'<p>{parts[1].strip()}</p>'
                    html += '</div>'
                else:
                    # Regular paragraph
                    html += f'<div class="section"><p>{section}</p></div>'
    
    html += '</div>'
    
    return html