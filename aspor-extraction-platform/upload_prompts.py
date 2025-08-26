#!/usr/bin/env python3
"""
Script to upload ASPOR prompts to AWS SSM Parameter Store
Usage: python upload_prompts.py [--region us-east-1]
"""

import boto3
import sys
import os
import argparse

def upload_prompts(region='us-east-1'):
    """Upload prompts from local files to SSM Parameter Store"""
    
    ssm_client = boto3.client('ssm', region_name=region)
    
    # Define prompts and their file paths
    prompts = {
        '/aspor/prompts/agent-a-contragarantias': '../../CONTRAGARANTIAS.txt',
        '/aspor/prompts/agent-b-informes': '../../INFORMES SOCIALES.txt'
    }
    
    success_count = 0
    
    for param_name, file_path in prompts.items():
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                continue
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()
            
            # Upload to SSM
            response = ssm_client.put_parameter(
                Name=param_name,
                Value=prompt_content,
                Type='String',
                Overwrite=True,
                Description=f'ASPOR prompt for {param_name.split("/")[-1]}'
            )
            
            print(f"✅ Successfully uploaded: {param_name}")
            print(f"   Version: {response['Version']}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ Error uploading {param_name}: {str(e)}")
    
    print(f"\n{'='*50}")
    print(f"Upload complete: {success_count}/{len(prompts)} prompts uploaded successfully")
    
    if success_count == len(prompts):
        print("✅ All prompts uploaded successfully!")
        return True
    else:
        print("⚠️  Some prompts failed to upload. Check the errors above.")
        return False

def verify_prompts(region='us-east-1'):
    """Verify that prompts are correctly stored in SSM"""
    
    ssm_client = boto3.client('ssm', region_name=region)
    
    param_names = [
        '/aspor/prompts/agent-a-contragarantias',
        '/aspor/prompts/agent-b-informes'
    ]
    
    print("\nVerifying prompts in SSM...")
    print("="*50)
    
    for param_name in param_names:
        try:
            response = ssm_client.get_parameter(
                Name=param_name,
                WithDecryption=False
            )
            
            param_value = response['Parameter']['Value']
            print(f"✅ {param_name}")
            print(f"   Size: {len(param_value)} characters")
            print(f"   First 100 chars: {param_value[:100]}...")
            
        except ssm_client.exceptions.ParameterNotFound:
            print(f"❌ {param_name} - NOT FOUND")
        except Exception as e:
            print(f"❌ {param_name} - ERROR: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Upload ASPOR prompts to AWS SSM')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing prompts')
    
    args = parser.parse_args()
    
    try:
        # Check AWS credentials
        sts = boto3.client('sts', region_name=args.region)
        caller_identity = sts.get_caller_identity()
        print(f"AWS Account: {caller_identity['Account']}")
        print(f"Region: {args.region}")
        print("="*50)
        
        if args.verify_only:
            verify_prompts(args.region)
        else:
            if upload_prompts(args.region):
                verify_prompts(args.region)
                return 0
            return 1
            
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nMake sure you have:")
        print("1. Configured AWS credentials (aws configure)")
        print("2. Proper IAM permissions for SSM")
        print("3. The prompt files in the correct location")
        return 1

if __name__ == '__main__':
    sys.exit(main())