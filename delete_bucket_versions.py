import boto3

bucket_name = 'aspor-documents-520754296204'
region = 'us-east-1'

s3 = boto3.client('s3', region_name=region)

# List and delete all object versions
paginator = s3.get_paginator('list_object_versions')
response_iterator = paginator.paginate(Bucket=bucket_name)

delete_count = 0

for page in response_iterator:
    delete_list = []
    
    # Add versions to delete list
    if 'Versions' in page:
        for version in page['Versions']:
            delete_list.append({'Key': version['Key'], 'VersionId': version['VersionId']})
            print(f"Deleting version: {version['Key']} - {version['VersionId']}")
    
    # Add delete markers to delete list
    if 'DeleteMarkers' in page:
        for marker in page['DeleteMarkers']:
            delete_list.append({'Key': marker['Key'], 'VersionId': marker['VersionId']})
            print(f"Deleting marker: {marker['Key']} - {marker['VersionId']}")
    
    # Delete in batches (max 1000 per request)
    if delete_list:
        response = s3.delete_objects(
            Bucket=bucket_name,
            Delete={'Objects': delete_list[:1000]}
        )
        delete_count += len(delete_list[:1000])
        print(f"Deleted batch of {len(delete_list[:1000])} objects")

print(f"\nTotal objects/versions deleted: {delete_count}")

# Now delete the bucket
try:
    s3.delete_bucket(Bucket=bucket_name)
    print(f"Bucket {bucket_name} deleted successfully")
except Exception as e:
    print(f"Error deleting bucket: {e}")