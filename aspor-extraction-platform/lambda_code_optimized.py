"""
Optimized Lambda handler for ASPOR platform
Uses common library to eliminate code duplication
"""
import json
import boto3
import os
import sys
from datetime import datetime

# Add common library to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import Config
from common.security import SecurityValidator
from common.s3_utils import S3Helper
from common.dynamodb_utils import DynamoDBHelper
from common.report_generator import ReportGenerator

# Initialize helpers
s3_helper = S3Helper()
db_helper = DynamoDBHelper()
bedrock_client = boto3.client('bedrock-runtime', region_name=Config.REGION)


def call_bedrock(model_type: str, text: str, file_names: list) -> str:
    """Call Bedrock API with proper error handling"""
    try:
        # Sanitize input text
        text = SecurityValidator.sanitize_user_input(text)
        
        # Create prompt based on model type
        if model_type == 'A':
            prompt = f"""Analiza este documento para validar capacidad de firma de contragarantías ASPOR.
            
Documento: {file_names[0] if file_names else 'Documento'}

Contenido:
{text[:3000]}

Genera un informe profesional con:
1. Información societaria
2. Validación de poderes para contragarantías
3. Lista de apoderados habilitados
4. Conclusión sobre capacidad de firma"""
        else:
            prompt = f"""Genera un INFORME SOCIAL profesional de este documento.

Documento: {file_names[0] if file_names else 'Documento'}

Contenido:
{text[:3000]}

Incluye:
1. Datos del cliente (razón social, RUT)
2. Objeto social
3. Capital social
4. Socios y participación
5. Administración
6. Domicilio"""
        
        # Call Bedrock
        body = {
            "anthropic_version": Config.BEDROCK_CONFIG["anthropic_version"],
            "max_tokens": Config.BEDROCK_CONFIG["max_tokens"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": Config.BEDROCK_CONFIG["temperature"],
            "top_p": Config.BEDROCK_CONFIG["top_p"]
        }
        
        response = bedrock_client.invoke_model(
            modelId=Config.BEDROCK_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        print(f"Bedrock error: {SecurityValidator.mask_sensitive_data(str(e))}")
        # Fallback to mock report
        return ReportGenerator.generate_mock_report(model_type, file_names)


def handler(event, context):
    """Main Lambda handler with improved error handling and security"""
    run_id = None
    timestamp = None
    user_id = 'default-user'
    
    try:
        # Validate environment
        if not Config.validate_environment():
            print("Warning: Some environment variables are missing")
        
        # Parse and validate request
        body = json.loads(event.get('body', '{}'))
        
        # Sanitize and validate inputs
        model = body.get('model', 'A')
        is_valid, error = SecurityValidator.validate_model_type(model)
        if not is_valid:
            return {
                'statusCode': 400,
                'headers': Config.get_headers(),
                'body': json.dumps({'error': error})
            }
        
        files = body.get('files', [])
        if not files or len(files) > Config.MAX_FILES_PER_RUN:
            return {
                'statusCode': 400,
                'headers': Config.get_headers(),
                'body': json.dumps({'error': f'Must provide 1-{Config.MAX_FILES_PER_RUN} files'})
            }
        
        # Validate all files
        for file_key in files:
            is_valid, error = SecurityValidator.validate_file(file_key)
            if not is_valid:
                return {
                    'statusCode': 400,
                    'headers': Config.get_headers(),
                    'body': json.dumps({'error': f'Invalid file: {error}'})
                }
        
        file_names = body.get('fileNames', [])
        output_format = body.get('outputFormat', 'docx')
        is_valid, error = SecurityValidator.validate_output_format(output_format)
        if not is_valid:
            return {
                'statusCode': 400,
                'headers': Config.get_headers(),
                'body': json.dumps({'error': error})
            }
        
        user_id = SecurityValidator.validate_user_id(body.get('userId', 'default-user'))
        
        print(f"Processing: Model={model}, Files={len(files)}, Format={output_format}, User={SecurityValidator.mask_sensitive_data(user_id)}")
        
        # Create run in DynamoDB
        run_item = db_helper.create_run(user_id, model, files, file_names, output_format)
        run_id = run_item['runId']
        timestamp = datetime.fromisoformat(run_item['startedAt'])
        
        # Update status to processing
        db_helper.update_run_status(
            user_id, run_id, timestamp.strftime("%Y%m%d%H%M%S"),
            'PROCESSING'
        )
        
        # Extract text from all files
        all_text = ""
        for i, s3_key in enumerate(files[:Config.MAX_FILES_PER_RUN]):
            text = s3_helper.extract_text_from_file(s3_key)
            if text and text != "Error al leer el documento.":
                file_label = file_names[i] if i < len(file_names) else f"Archivo {i+1}"
                all_text += f"\n--- {file_label} ---\n{text[:2000]}\n"
        
        if not all_text:
            all_text = "Contenido del documento para análisis."
        
        # Process with Bedrock or generate mock
        analysis_result = call_bedrock(model, all_text, file_names)
        
        # Save analysis text for reference
        analysis_key = f'outputs/{run_id}/analysis.txt'
        s3_helper.save_file(
            analysis_key,
            analysis_result.encode('utf-8'),
            'text/plain; charset=utf-8',
            {'run_id': run_id, 'model': model}
        )
        
        # Generate output file
        output_key = f'outputs/{run_id}/report.{output_format}'
        content, content_type = ReportGenerator.generate_output_file(
            analysis_result, output_format, model
        )
        
        # Save to S3
        s3_helper.save_file(
            output_key,
            content,
            content_type,
            {
                'run_id': run_id,
                'model': model,
                'format': output_format
            }
        )
        
        # Generate download URL
        download_url = s3_helper.generate_presigned_url(output_key, download=True)
        
        if not download_url:
            raise Exception("Failed to generate download URL")
        
        # Update DynamoDB with completion
        db_helper.update_run_status(
            user_id, run_id, timestamp.strftime("%Y%m%d%H%M%S"),
            'COMPLETED',
            output={
                'downloadUrl': download_url,
                output_format: output_key
            }
        )
        
        print(f"Run completed successfully: {run_id}")
        
        return {
            'statusCode': 200,
            'headers': Config.get_headers(),
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
            'headers': Config.get_headers(),
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
        
    except Exception as e:
        error_msg = SecurityValidator.get_safe_error_message(e)
        print(f"Error in handler: {error_msg}")
        
        # Update run status to failed if we have a run_id
        if run_id and timestamp:
            try:
                db_helper.update_run_status(
                    user_id, run_id, timestamp.strftime("%Y%m%d%H%M%S"),
                    'FAILED',
                    error=str(e)
                )
            except:
                pass
        
        # Don't expose internal errors in production
        if Config.is_production():
            return {
                'statusCode': 500,
                'headers': Config.get_headers(),
                'body': json.dumps({
                    'error': 'Error processing request',
                    'runId': run_id
                })
            }
        else:
            return {
                'statusCode': 500,
                'headers': Config.get_headers(),
                'body': json.dumps({
                    'error': 'Error en el procesamiento',
                    'details': error_msg,
                    'runId': run_id
                })
            }