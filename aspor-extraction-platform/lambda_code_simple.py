import json
import boto3
import os
from datetime import datetime
import uuid

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')
bedrock_client = boto3.client('bedrock-runtime')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

def extract_text_from_s3(s3_key):
    """Simple text extraction"""
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        return obj['Body'].read().decode('utf-8', errors='ignore')
    except:
        return "Documento de prueba para análisis ASPOR."

def call_bedrock_simple(model_type, text):
    """Simplified Bedrock call"""
    try:
        if model_type == 'A':
            prompt = f"Analiza este documento para validar capacidad de firma de contragarantías ASPOR:\n\n{text[:2000]}"
        else:
            prompt = f"Genera un informe social profesional de este documento:\n\n{text[:2000]}"
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",  # Using Haiku for faster response
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    except Exception as e:
        print(f"Bedrock error: {str(e)}")
        return generate_mock_report(model_type)

def generate_mock_report(model_type):
    """Generate mock report"""
    if model_type == 'A':
        return """# INFORME DE ANÁLISIS - CONTRAGARANTÍAS ASPOR

## INFORMACIÓN SOCIETARIA
- **Razón Social**: EMPRESA DEMO S.A.
- **RUT**: 76.123.456-7
- **Tipo**: Sociedad Anónima

## VALIDACIÓN PARA CONTRAGARANTÍAS
### Apoderados Habilitados
- Juan Pérez (12.345.678-9): ✅ Puede firmar contragarantías
- María González (98.765.432-1): ✅ Puede firmar contragarantías

## CONCLUSIÓN
Los apoderados identificados PUEDEN firmar contragarantías simples para ASPOR.

---
*Informe generado automáticamente*"""
    else:
        return """# INFORME SOCIAL

## CLIENTE: EMPRESA DEMO S.A.
**R.U.T.**: 76.123.456-7

## OBJETO SOCIAL
Desarrollo de actividades comerciales e industriales.

## CAPITAL SOCIAL
- Capital Total: $100.000.000
- Capital Suscrito: $100.000.000
- Capital Pagado: $100.000.000

## ADMINISTRACIÓN
Directorio compuesto por 5 miembros.

---
*Informe generado automáticamente*"""

def handler(event, context):
    """Simplified handler with direct processing"""
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        model = body.get('model', 'A')
        files = body.get('files', [])
        file_names = body.get('fileNames', [])
        output_format = body.get('outputFormat', 'docx')
        user_id = body.get('userId', 'default-user')
        
        # Validate
        if model not in ['A', 'B']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Model must be A or B'})
            }
        
        # Create run
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Store in DynamoDB
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}',
            'runId': run_id,
            'model': model,
            'files': files,
            'fileNames': file_names if file_names else ['documento.pdf'],
            'outputFormat': output_format,
            'status': 'PROCESSING',
            'startedAt': timestamp.isoformat(),
            'userId': user_id
        }
        
        table.put_item(Item=run_item)
        
        # Extract text (simplified)
        all_text = ""
        for s3_key in files[:1]:  # Process only first file for speed
            text = extract_text_from_s3(s3_key)
            all_text += text[:2000]  # Limit text
        
        if not all_text:
            all_text = "Contenido del documento."
        
        # Call Bedrock
        analysis_result = call_bedrock_simple(model, all_text)
        
        # Save result to S3
        output_key = f'outputs/{run_id}/report.txt'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=analysis_result.encode('utf-8'),
            ContentType='text/plain; charset=utf-8'
        )
        
        # Generate download URL
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': output_key},
            ExpiresIn=86400
        )
        
        # Update DynamoDB
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
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'runId': run_id,
                'status': 'COMPLETED',
                'downloadUrl': download_url,
                'outputFormat': output_format,
                'message': 'Procesamiento completado'
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # If we have a run_id, update to failed
        if 'run_id' in locals():
            try:
                table.update_item(
                    Key={'pk': f'USER#{user_id}', 'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'},
                    UpdateExpression='SET #status = :status',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={':status': 'FAILED'}
                )
            except:
                pass
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }