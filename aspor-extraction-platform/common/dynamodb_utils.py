"""
DynamoDB utilities for ASPOR platform
"""
import boto3
from boto3.dynamodb.conditions import Key, Attr
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from .config import Config
from .security import SecurityValidator


class DynamoDBHelper:
    """DynamoDB operations helper with consistent error handling"""
    
    def __init__(self, table_name: str = None):
        dynamodb = boto3.resource('dynamodb', region_name=Config.REGION)
        self.table_name = table_name or Config.DYNAMODB_TABLE
        self.table = dynamodb.Table(self.table_name)
    
    def create_run(self, user_id: str, model: str, files: List[str], 
                   file_names: List[str], output_format: str = 'docx') -> Dict[str, Any]:
        """Create a new run entry in DynamoDB"""
        # Validate inputs
        user_id = SecurityValidator.validate_user_id(user_id)
        is_valid, error = SecurityValidator.validate_model_type(model)
        if not is_valid:
            raise ValueError(error)
        
        is_valid, error = SecurityValidator.validate_output_format(output_format)
        if not is_valid:
            raise ValueError(error)
        
        # Generate IDs and timestamp
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Create item
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}',
            'runId': run_id,
            'model': model,
            'files': files[:Config.MAX_FILES_PER_RUN],  # Limit files
            'fileNames': file_names[:Config.MAX_FILES_PER_RUN] if file_names else ['documento.pdf'],
            'outputFormat': output_format,
            'status': 'PENDING',
            'startedAt': timestamp.isoformat(),
            'userId': user_id,
            'gsi1pk': 'ALL_RUNS',
            'gsi1sk': f'{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
        }
        
        self.table.put_item(Item=run_item)
        return run_item
    
    def get_run(self, user_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific run by ID"""
        user_id = SecurityValidator.validate_user_id(user_id)
        is_valid, error = SecurityValidator.validate_run_id(run_id)
        if not is_valid:
            raise ValueError(error)
        
        # Query for the run
        response = self.table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#')
        )
        
        # Find matching run
        for item in response.get('Items', []):
            if item.get('runId') == run_id:
                return item
        
        return None
    
    def update_run_status(self, user_id: str, run_id: str, timestamp_str: str,
                          status: str, output: Dict[str, Any] = None, error: str = None):
        """Update run status in DynamoDB"""
        user_id = SecurityValidator.validate_user_id(user_id)
        
        update_expr_parts = ['SET #status = :status']
        expr_names = {'#status': 'status'}
        expr_values = {':status': status}
        
        if status == 'COMPLETED' and output:
            update_expr_parts.append('#output = :output')
            update_expr_parts.append('#endedAt = :endedAt')
            expr_names['#output'] = 'output'
            expr_names['#endedAt'] = 'endedAt'
            expr_values[':output'] = output
            expr_values[':endedAt'] = datetime.utcnow().isoformat()
        
        if status == 'FAILED' and error:
            update_expr_parts.append('#error = :error')
            update_expr_parts.append('#endedAt = :endedAt')
            expr_names['#error'] = 'error'
            expr_names['#endedAt'] = 'endedAt'
            expr_values[':error'] = SecurityValidator.get_safe_error_message(Exception(error))
            expr_values[':endedAt'] = datetime.utcnow().isoformat()
        
        self.table.update_item(
            Key={
                'pk': f'USER#{user_id}',
                'sk': f'RUN#{timestamp_str}#{run_id}'
            },
            UpdateExpression=', '.join(update_expr_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
    
    def list_runs(self, user_id: str, limit: int = 20, 
                  last_evaluated_key: Dict[str, Any] = None) -> Dict[str, Any]:
        """List runs for a user with pagination"""
        user_id = SecurityValidator.validate_user_id(user_id)
        
        query_kwargs = {
            'KeyConditionExpression': Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            'ScanIndexForward': False,  # Most recent first
            'Limit': min(limit, 100)  # Cap at 100
        }
        
        if last_evaluated_key:
            query_kwargs['ExclusiveStartKey'] = last_evaluated_key
        
        response = self.table.query(**query_kwargs)
        
        # Clean up items for response
        runs = []
        for item in response.get('Items', []):
            runs.append({
                'runId': item.get('runId'),
                'model': item.get('model'),
                'status': item.get('status'),
                'startedAt': item.get('startedAt'),
                'endedAt': item.get('endedAt'),
                'fileNames': item.get('fileNames', []),
                'outputFormat': item.get('outputFormat')
            })
        
        result = {
            'runs': runs,
            'count': len(runs),
            'hasMore': 'LastEvaluatedKey' in response
        }
        
        if 'LastEvaluatedKey' in response:
            result['lastEvaluatedKey'] = response['LastEvaluatedKey']
        
        return result
    
    def delete_run(self, user_id: str, run_id: str) -> bool:
        """Delete a run from DynamoDB"""
        user_id = SecurityValidator.validate_user_id(user_id)
        is_valid, error = SecurityValidator.validate_run_id(run_id)
        if not is_valid:
            raise ValueError(error)
        
        # Find the run first
        run = self.get_run(user_id, run_id)
        if not run:
            return False
        
        # Extract timestamp from SK
        sk_parts = run['sk'].split('#')
        timestamp_str = sk_parts[1]
        
        # Delete from DynamoDB
        self.table.delete_item(
            Key={
                'pk': f'USER#{user_id}',
                'sk': f'RUN#{timestamp_str}#{run_id}'
            }
        )
        
        return True
    
    def get_user_stats(self, user_id: str) -> Dict[str, int]:
        """Get user statistics"""
        user_id = SecurityValidator.validate_user_id(user_id)
        
        response = self.table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            Select='COUNT'
        )
        
        total_runs = response.get('Count', 0)
        
        # Get status counts
        response = self.table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#')
        )
        
        status_counts = {
            'total': total_runs,
            'completed': 0,
            'failed': 0,
            'processing': 0
        }
        
        for item in response.get('Items', []):
            status = item.get('status', '').lower()
            if status == 'completed':
                status_counts['completed'] += 1
            elif status == 'failed':
                status_counts['failed'] += 1
            elif status in ['processing', 'pending']:
                status_counts['processing'] += 1
        
        return status_counts