#!/usr/bin/env python3
"""
Script de verificación pre-despliegue para ASPOR Platform
Verifica configuración, permisos y optimizaciones antes de desplegar en AWS
"""

import json
import yaml
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess

class PreDeploymentChecker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.checks_passed = 0
        self.checks_failed = 0
        
    def print_header(self, title: str):
        """Print formatted section header"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    def print_result(self, status: str, message: str, detail: str = None):
        """Print formatted result"""
        symbols = {'✅': '[OK]', '❌': '[ERROR]', '⚠️': '[WARN]', 'ℹ️': '[INFO]'}
        symbol = symbols.get(status, status)
        print(f"{symbol} {message}")
        if detail:
            print(f"      {detail}")
    
    def check_aws_cli(self) -> bool:
        """Verify AWS CLI is installed and configured"""
        self.print_header("1. AWS CLI Configuration")
        
        try:
            # Check AWS CLI installation
            result = subprocess.run(['aws', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                self.print_result('✅', f"AWS CLI installed: {version}")
                self.checks_passed += 1
            else:
                self.print_result('❌', "AWS CLI not found")
                self.errors.append("Install AWS CLI: https://aws.amazon.com/cli/")
                self.checks_failed += 1
                return False
                
            # Check AWS credentials
            result = subprocess.run(['aws', 'sts', 'get-caller-identity'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                identity = json.loads(result.stdout)
                self.print_result('✅', f"AWS Account: {identity['Account']}")
                self.print_result('ℹ️', f"User/Role: {identity['Arn'].split('/')[-1]}")
                self.checks_passed += 1
                return True
            else:
                self.print_result('❌', "AWS credentials not configured")
                self.errors.append("Run: aws configure")
                self.checks_failed += 1
                return False
                
        except Exception as e:
            self.print_result('❌', f"Error checking AWS CLI: {str(e)}")
            self.checks_failed += 1
            return False
    
    def check_sam_cli(self) -> bool:
        """Verify SAM CLI is installed"""
        self.print_header("2. SAM CLI Configuration")
        
        try:
            result = subprocess.run(['sam', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.print_result('✅', f"SAM CLI installed: {version}")
                self.checks_passed += 1
                return True
            else:
                self.print_result('❌', "SAM CLI not found")
                self.errors.append("Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html")
                self.checks_failed += 1
                return False
        except:
            self.print_result('❌', "SAM CLI not installed")
            self.checks_failed += 1
            return False
    
    def check_template_yaml(self) -> bool:
        """Verify and analyze SAM template"""
        self.print_header("3. SAM Template Analysis")
        
        template_path = Path('template.yaml')
        if not template_path.exists():
            self.print_result('❌', "template.yaml not found")
            self.checks_failed += 1
            return False
        
        try:
            with open(template_path, 'r') as f:
                template = yaml.safe_load(f)
            
            # Check Lambda configurations
            resources = template.get('Resources', {})
            lambda_functions = {k: v for k, v in resources.items() 
                              if v.get('Type') == 'AWS::Serverless::Function'}
            
            self.print_result('✅', f"Found {len(lambda_functions)} Lambda functions")
            
            # Analyze each Lambda function
            for name, config in lambda_functions.items():
                props = config.get('Properties', {})
                timeout = props.get('Timeout', 3)
                memory = props.get('MemorySize', 128)
                
                # Check timeouts
                if name == 'CreateRunFunction':
                    if timeout < 900:
                        self.print_result('⚠️', f"{name}: Timeout={timeout}s (recommend 900s for Bedrock)")
                        self.warnings.append(f"Increase {name} timeout to 900s")
                    else:
                        self.print_result('✅', f"{name}: Timeout={timeout}s")
                    
                    if memory < 3008:
                        self.print_result('⚠️', f"{name}: Memory={memory}MB (recommend 3008MB)")
                        self.warnings.append(f"Increase {name} memory to 3008MB")
                    else:
                        self.print_result('✅', f"{name}: Memory={memory}MB")
                else:
                    self.print_result('ℹ️', f"{name}: Timeout={timeout}s, Memory={memory}MB")
            
            # Check IAM policies
            self.print_result('ℹ️', "Checking IAM Policies...")
            for name, config in lambda_functions.items():
                policies = config.get('Properties', {}).get('Policies', [])
                self.print_result('ℹ️', f"  {name}: {len(policies)} policies attached")
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.print_result('❌', f"Error parsing template.yaml: {str(e)}")
            self.checks_failed += 1
            return False
    
    def check_python_dependencies(self) -> bool:
        """Check Python dependencies"""
        self.print_header("4. Python Dependencies")
        
        requirements_path = Path('requirements.txt')
        if not requirements_path.exists():
            self.print_result('❌', "requirements.txt not found")
            self.checks_failed += 1
            return False
        
        with open(requirements_path, 'r') as f:
            deps = f.read().strip().split('\n')
        
        self.print_result('✅', f"Found {len(deps)} dependencies")
        for dep in deps:
            self.print_result('ℹ️', f"  - {dep}")
        
        # Check critical dependencies versions
        critical_deps = {
            'boto3': '1.28.0',
            'PyPDF2': '3.0.0',
            'python-docx': '1.0.0'
        }
        
        for dep_line in deps:
            for critical_dep, min_version in critical_deps.items():
                if critical_dep in dep_line:
                    self.print_result('✅', f"{critical_dep} included")
        
        self.checks_passed += 1
        return True
    
    def check_file_structure(self) -> bool:
        """Verify all required files exist"""
        self.print_header("5. File Structure Verification")
        
        required_files = [
            'template.yaml',
            'requirements.txt',
            'deploy.sh',
            'samconfig.toml',
            'src/__init__.py',
            'src/handlers/presign.py',
            'src/handlers/create_run.py',
            'src/handlers/get_run.py',
            'src/handlers/list_runs.py',
            'src/handlers/delete_run.py',
            'src/processors/document_processor.py',
            'src/processors/bedrock_agent.py',
            'src/generators/report_generator.py',
            'frontend/index.html',
            '../CONTRAGARANTIAS.txt',
            '../INFORMES SOCIALES.txt'
        ]
        
        missing_files = []
        for file_path in required_files:
            path = Path(file_path)
            if path.exists():
                self.print_result('✅', f"{file_path}")
            else:
                self.print_result('❌', f"{file_path} - MISSING")
                missing_files.append(file_path)
        
        if missing_files:
            self.errors.append(f"Missing {len(missing_files)} required files")
            self.checks_failed += 1
            return False
        else:
            self.print_result('✅', "All required files present")
            self.checks_passed += 1
            return True
    
    def estimate_deployment(self) -> None:
        """Estimate deployment time and costs"""
        self.print_header("6. Deployment Estimates")
        
        # Time estimates
        self.print_result('ℹ️', "Estimated Deployment Time:")
        print("      - SAM Build: 2-3 minutes")
        print("      - Stack Creation: 5-7 minutes")
        print("      - Total: ~10 minutes")
        
        # Cost estimates
        self.print_result('ℹ️', "Estimated Monthly Costs (100 documents):")
        print("      - Lambda: ~$0.50")
        print("      - S3: ~$2.00")
        print("      - DynamoDB: ~$1.00")
        print("      - API Gateway: ~$1.00")
        print("      - Bedrock: ~$15.00 (varies by usage)")
        print("      - Total: ~$20-25/month")
        
        # Resource counts
        self.print_result('ℹ️', "Resources to be created:")
        print("      - 5 Lambda Functions")
        print("      - 2 S3 Buckets")
        print("      - 1 DynamoDB Table")
        print("      - 1 API Gateway")
        print("      - 1 CloudFront Distribution")
        print("      - 2 SSM Parameters")
        print("      - Multiple IAM Roles & Policies")
    
    def check_iam_permissions_needed(self) -> None:
        """List required IAM permissions for deployment"""
        self.print_header("7. Required IAM Permissions")
        
        required_services = [
            "cloudformation:*",
            "lambda:*",
            "apigateway:*",
            "s3:*",
            "dynamodb:*",
            "iam:*",
            "ssm:PutParameter",
            "ssm:GetParameter",
            "cloudfront:*",
            "bedrock:InvokeModel",
            "textract:DetectDocumentText"
        ]
        
        self.print_result('ℹ️', "Your AWS user/role needs permissions for:")
        for service in required_services:
            print(f"      - {service}")
        
        self.print_result('⚠️', "Recommendation: Use AdministratorAccess for deployment")
        self.warnings.append("After deployment, create a restricted role for operations")
    
    def generate_optimized_template(self) -> None:
        """Generate optimized template with recommendations"""
        self.print_header("8. Generating Optimizations")
        
        try:
            with open('template.yaml', 'r') as f:
                content = f.read()
            
            # Apply optimizations
            optimizations = [
                ('Timeout: 300', 'Timeout: 900  # Increased for Bedrock processing'),
                ('MemorySize: 128', 'MemorySize: 3008  # Optimized for document processing'),
            ]
            
            optimized_content = content
            for old, new in optimizations:
                if old in content:
                    optimized_content = optimized_content.replace(old, new)
                    self.print_result('✅', f"Applied: {new.split('#')[1].strip()}")
            
            # Save optimized template
            with open('template.optimized.yaml', 'w') as f:
                f.write(optimized_content)
            
            self.print_result('✅', "Created template.optimized.yaml with optimizations")
            self.info.append("Use template.optimized.yaml for better performance")
            
        except Exception as e:
            self.print_result('⚠️', f"Could not optimize template: {str(e)}")
    
    def run_all_checks(self) -> bool:
        """Run all pre-deployment checks"""
        print("\n" + "="*60)
        print("   ASPOR PLATFORM - PRE-DEPLOYMENT VERIFICATION")
        print("="*60)
        
        # Run checks
        aws_ok = self.check_aws_cli()
        sam_ok = self.check_sam_cli()
        template_ok = self.check_template_yaml()
        deps_ok = self.check_python_dependencies()
        files_ok = self.check_file_structure()
        
        # Additional information
        self.estimate_deployment()
        self.check_iam_permissions_needed()
        self.generate_optimized_template()
        
        # Summary
        self.print_header("VERIFICATION SUMMARY")
        
        print(f"\n✅ Checks Passed: {self.checks_passed}")
        print(f"❌ Checks Failed: {self.checks_failed}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        if self.warnings:
            print(f"\n⚠️ WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if self.info:
            print(f"\nℹ️ RECOMMENDATIONS ({len(self.info)}):")
            for info in self.info:
                print(f"   - {info}")
        
        # Final verdict
        print("\n" + "="*60)
        if self.checks_failed == 0:
            print("✅ READY FOR DEPLOYMENT!")
            print("\nNext steps:")
            print("1. Review warnings above (if any)")
            print("2. Ensure Bedrock Claude is enabled in your AWS account")
            print("3. Run: sam build && sam deploy --guided")
            return True
        else:
            print("❌ NOT READY FOR DEPLOYMENT")
            print(f"\nFix {self.checks_failed} errors before proceeding")
            return False

def main():
    """Main execution"""
    checker = PreDeploymentChecker()
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Run checks
    ready = checker.run_all_checks()
    
    # Exit with appropriate code
    sys.exit(0 if ready else 1)

if __name__ == '__main__':
    main()