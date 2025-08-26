import json
import boto3
import os
from datetime import datetime
import uuid
from ..processors.document_processor import DocumentProcessor
from ..processors.bedrock_agent import BedrockAgent
from ..generators.report_generator import ReportGenerator

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ['DYNAMODB_TABLE']
bucket_name = os.environ['DOCUMENTS_BUCKET']
table = dynamodb.Table(table_name)

def handler(event, context):
    """Create and process a new extraction run"""
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        model = body.get('model')  # 'A' or 'B'
        files = body.get('files', [])
        output_format = body.get('outputFormat', 'docx')
        user_id = body.get('userId', 'default-user')  # In production, get from auth token
        
        # Validate inputs
        if model not in ['A', 'B']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Model must be A or B'})
            }
        
        if not files or len(files) > int(os.environ.get('MAX_FILES', 3)):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': f'Must provide 1-{os.environ.get("MAX_FILES", 3)} files'})
            }
        
        # Create run ID
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Create DynamoDB entry
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}',
            'runId': run_id,
            'model': model,
            'files': files,
            'outputFormat': output_format,
            'status': 'RUNNING',
            'startedAt': timestamp.isoformat(),
            'userId': user_id,
            'gsi1pk': 'ALL_RUNS',
            'gsi1sk': f'{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
        }
        
        table.put_item(Item=run_item)
        
        try:
            # Process documents
            processor = DocumentProcessor(bucket_name, s3_client)
            extracted_texts = []
            
            for file_key in files:
                text = processor.extract_text(file_key)
                extracted_texts.append({
                    'file': file_key,
                    'text': text
                })
            
            # Call Bedrock with appropriate agent
            bedrock_agent = BedrockAgent()
            
            if model == 'A':
                result = bedrock_agent.process_contragarantias(extracted_texts)
            else:
                result = bedrock_agent.process_informes_sociales(extracted_texts)
            
            # Generate report
            generator = ReportGenerator(bucket_name, s3_client)
            
            if output_format == 'docx':
                output_key = f'outputs/{run_id}/report.docx'
                generator.generate_docx(result, output_key, model)
            else:
                output_key = f'outputs/{run_id}/report.pdf'
                generator.generate_pdf(result, output_key, model)
            
            # Generate presigned URL for download
            download_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': output_key},
                ExpiresIn=86400  # 24 hours
            )
            
            # Update DynamoDB with completion
            table.update_item(
                Key={
                    'pk': f'USER#{user_id}',
                    'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
                },
                UpdateExpression='SET #status = :status, #output = :output, #endedAt = :endedAt, #metrics = :metrics',
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#output': 'output',
                    '#endedAt': 'endedAt',
                    '#metrics': 'metrics'
                },
                ExpressionAttributeValues={
                    ':status': 'COMPLETED',
                    ':output': {
                        output_format: output_key,
                        'downloadUrl': download_url
                    },
                    ':endedAt': datetime.utcnow().isoformat(),
                    ':metrics': result.get('metrics', {})
                }
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'runId': run_id,
                    'status': 'COMPLETED',
                    'downloadUrl': download_url,
                    'outputFormat': output_format
                })
            }
            
        except Exception as process_error:
            print(f"Processing error: {str(process_error)}")
            
            # Update status to FAILED
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
                    ':error': str(process_error),
                    ':endedAt': datetime.utcnow().isoformat()
                }
            )
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'runId': run_id,
                    'status': 'FAILED',
                    'error': 'Processing failed'
                })
            }
        
    except Exception as e:
        print(f"Error creating run: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }