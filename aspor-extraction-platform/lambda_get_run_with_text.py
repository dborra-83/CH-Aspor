import json
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
}

def handler(event, context):
    """Get details of a specific run including analysis text"""
    
    # Handle OPTIONS request for CORS preflight
    if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''
        }
    
    try:
        run_id = event.get('pathParameters', {}).get('runId')
        user_id = event.get('queryStringParameters', {}).get('userId', 'web-user')
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Run ID is required'})
            }
        
        print(f"Fetching run {run_id} for user {user_id}")
        
        # Query for the run using filter
        response = table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            FilterExpression=Attr('runId').eq(run_id)
        )
        
        if not response['Items']:
            return {
                'statusCode': 404,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Run not found'})
            }
        
        run = response['Items'][0]
        
        # Try to get analysis text from S3 if run is completed
        analysis_text = None
        if run.get('status') == 'COMPLETED':
            try:
                analysis_key = f'outputs/{run_id}/analysis.txt'
                print(f"Attempting to fetch analysis from S3: {analysis_key}")
                
                analysis_obj = s3_client.get_object(
                    Bucket=bucket_name,
                    Key=analysis_key
                )
                analysis_text = analysis_obj['Body'].read().decode('utf-8')
                print(f"Successfully retrieved analysis text: {len(analysis_text)} characters")
                
            except Exception as e:
                print(f"Could not retrieve analysis text: {str(e)}")
                # Not critical - analysis might not be saved as text file
        
        # Generate fresh download URLs if output exists
        if run.get('output') and run.get('status') == 'COMPLETED':
            output = run['output']
            # Handle both dict and string formats
            if isinstance(output, dict):
                for format_type, s3_key in output.items():
                    if format_type in ['docx', 'pdf'] and s3_key:
                        try:
                            url = s3_client.generate_presigned_url(
                                'get_object',
                                Params={
                                    'Bucket': bucket_name,
                                    'Key': s3_key,
                                    'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                                },
                                ExpiresIn=3600
                            )
                            run[f'{format_type}DownloadUrl'] = url
                            
                            # Set the main downloadUrl based on output format
                            if format_type == run.get('outputFormat', 'docx'):
                                run['downloadUrl'] = url
                        except Exception as e:
                            print(f"Error generating presigned URL for {format_type}: {str(e)}")
            elif isinstance(output, str):
                # Legacy format - single S3 key
                try:
                    format_type = run.get('outputFormat', 'docx')
                    url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': bucket_name,
                            'Key': output,
                            'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                        },
                        ExpiresIn=3600
                    )
                    run['downloadUrl'] = url
                except Exception as e:
                    print(f"Error generating presigned URL: {str(e)}")
        
        # Add analysis text to response if available
        if analysis_text:
            run['analysisText'] = analysis_text
        
        # Clean up the response - remove internal fields
        run.pop('pk', None)
        run.pop('sk', None)
        run.pop('gsi1pk', None)
        run.pop('gsi1sk', None)
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps(run)
        }
        
    except Exception as e:
        print(f"Error getting run: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)[:200] if not os.environ.get('PRODUCTION') else None
            })
        }