#!/bin/bash

# Quick Check Script for ASPOR Deployment Readiness

echo "================================================"
echo "  ASPOR PLATFORM - QUICK DEPLOYMENT CHECK"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check functions
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is NOT installed"
        return 1
    fi
}

check_aws_config() {
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
        echo -e "${GREEN}✓${NC} AWS configured - Account: $ACCOUNT_ID"
        echo "   User/Role: $USER_ARN"
        return 0
    else
        echo -e "${RED}✗${NC} AWS credentials not configured"
        echo "   Run: aws configure"
        return 1
    fi
}

check_bedrock() {
    echo "Checking Bedrock access..."
    if aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude')]" --output json 2>/dev/null | grep -q "claude"; then
        echo -e "${GREEN}✓${NC} Bedrock Claude models available"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} Bedrock Claude not accessible or not enabled"
        echo "   Enable at: https://console.aws.amazon.com/bedrock/"
        return 1
    fi
}

check_files() {
    local missing=0
    echo "Checking required files..."
    
    files=(
        "aspor-extraction-platform/template.yaml"
        "aspor-extraction-platform/requirements.txt"
        "aspor-extraction-platform/deploy.sh"
        "CONTRAGARANTIAS.txt"
        "INFORMES SOCIALES.txt"
    )
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            echo -e "${GREEN}✓${NC} $file"
        else
            echo -e "${RED}✗${NC} $file missing"
            missing=$((missing + 1))
        fi
    done
    
    return $missing
}

estimate_costs() {
    echo ""
    echo "ESTIMATED COSTS (Monthly for 100 documents):"
    echo "  Lambda:       ~\$0.50"
    echo "  S3:           ~\$2.00"
    echo "  DynamoDB:     ~\$1.00"
    echo "  API Gateway:  ~\$1.00"
    echo "  Bedrock:      ~\$15.00"
    echo "  CloudFront:   ~\$1.00"
    echo "  -------------------------"
    echo "  TOTAL:        ~\$20-25/month"
}

estimate_time() {
    echo ""
    echo "DEPLOYMENT TIME ESTIMATES:"
    echo "  SAM Build:     2-3 minutes"
    echo "  Stack Deploy:  5-7 minutes"
    echo "  Prompt Upload: 1 minute"
    echo "  -------------------------"
    echo "  TOTAL:         ~10 minutes"
}

# Main execution
echo ""
echo "1. CHECKING TOOLS..."
echo "--------------------"
TOOLS_OK=true
check_command "aws" || TOOLS_OK=false
check_command "sam" || TOOLS_OK=false
check_command "python3" || TOOLS_OK=false
check_command "git" || TOOLS_OK=false

echo ""
echo "2. CHECKING AWS..."
echo "------------------"
AWS_OK=true
check_aws_config || AWS_OK=false
check_bedrock || AWS_OK=false

echo ""
echo "3. CHECKING FILES..."
echo "--------------------"
check_files
FILES_OK=$?

echo ""
echo "4. DEPLOYMENT INFO..."
echo "---------------------"
estimate_time
estimate_costs

echo ""
echo "================================================"
echo "                   SUMMARY"
echo "================================================"

if [ "$TOOLS_OK" = true ] && [ "$AWS_OK" = true ] && [ $FILES_OK -eq 0 ]; then
    echo -e "${GREEN}✓ READY FOR DEPLOYMENT!${NC}"
    echo ""
    echo "NEXT STEPS:"
    echo "1. cd aspor-extraction-platform"
    echo "2. sam build"
    echo "3. sam deploy --guided"
    echo "4. python upload_prompts.py"
else
    echo -e "${RED}✗ NOT READY FOR DEPLOYMENT${NC}"
    echo ""
    echo "FIX THE ISSUES ABOVE BEFORE PROCEEDING"
fi

echo ""
echo "For detailed checks, run:"
echo "  python aspor-extraction-platform/pre-deploy-check.py"
echo "================================================"