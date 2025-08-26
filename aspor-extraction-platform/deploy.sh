#!/bin/bash

# ASPOR Extraction Platform - Deployment Script
# Usage: ./deploy.sh [stack-name] [region]

STACK_NAME=${1:-aspor-extraction-platform}
REGION=${2:-us-east-1}
PROMPTS_DIR="../../"

echo "=========================================="
echo "ASPOR Extraction Platform - Deployment"
echo "=========================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check for SAM CLI
if ! command -v sam &> /dev/null; then
    echo "Error: SAM CLI is not installed"
    exit 1
fi

# Check AWS credentials
echo "Checking AWS credentials..."
aws sts get-caller-identity --region $REGION > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: AWS credentials not configured"
    exit 1
fi

# Build the SAM application
echo "Building SAM application..."
sam build --region $REGION

if [ $? -ne 0 ]; then
    echo "Error: SAM build failed"
    exit 1
fi

# Deploy the SAM application
echo "Deploying SAM application..."
sam deploy \
    --stack-name $STACK_NAME \
    --region $REGION \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides BedrockModelId="anthropic.claude-3-opus-20240229" \
    --no-fail-on-empty-changeset

if [ $? -ne 0 ]; then
    echo "Error: SAM deployment failed"
    exit 1
fi

# Get stack outputs
echo ""
echo "Getting stack outputs..."
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
    --output text)

WEBSITE_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
    --output text)

WEBSITE_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" \
    --output text)

# Update frontend with API URL
echo "Updating frontend configuration..."
sed -i.bak "s|https://your-api-gateway-url.execute-api.region.amazonaws.com/prod|$API_URL|g" frontend/index.html

# Upload frontend to S3
echo "Uploading frontend to S3..."
aws s3 cp frontend/index.html s3://$WEBSITE_BUCKET/ --region $REGION

# Update SSM Parameters with actual prompts
echo "Updating prompt parameters..."

# Read Agent A prompt
if [ -f "$PROMPTS_DIR/CONTRAGARANTIAS.txt" ]; then
    echo "Updating Agent A prompt..."
    AGENT_A_PROMPT=$(<"$PROMPTS_DIR/CONTRAGARANTIAS.txt")
    aws ssm put-parameter \
        --name "/aspor/prompts/agent-a-contragarantias" \
        --value "$AGENT_A_PROMPT" \
        --type "String" \
        --overwrite \
        --region $REGION
fi

# Read Agent B prompt
if [ -f "$PROMPTS_DIR/INFORMES SOCIALES.txt" ]; then
    echo "Updating Agent B prompt..."
    AGENT_B_PROMPT=$(<"$PROMPTS_DIR/INFORMES SOCIALES.txt")
    aws ssm put-parameter \
        --name "/aspor/prompts/agent-b-informes" \
        --value "$AGENT_B_PROMPT" \
        --type "String" \
        --overwrite \
        --region $REGION
fi

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "API Endpoint: $API_URL"
echo "Website URL: $WEBSITE_URL"
echo ""
echo "Next steps:"
echo "1. Enable Bedrock Claude model in your AWS account if not already enabled"
echo "2. Test the API endpoints using the provided Postman collection"
echo "3. Access the web interface at: $WEBSITE_URL"
echo ""