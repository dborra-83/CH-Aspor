# ASPOR Platform Deployment Script for Windows PowerShell
# Usage: .\deploy-windows.ps1

param(
    [string]$StackName = "aspor-platform",
    [string]$Region = "us-east-1"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ASPOR PLATFORM DEPLOYMENT - WINDOWS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stack Name: $StackName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""

# Function to check command availability
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Check prerequisites
Write-Host "CHECKING PREREQUISITES..." -ForegroundColor Cyan

# Check AWS CLI
if (Test-Command "aws") {
    $awsVersion = aws --version
    Write-Host "[OK] AWS CLI installed: $awsVersion" -ForegroundColor Green
} else {
    Write-Host "[ERROR] AWS CLI not found. Please install from: https://aws.amazon.com/cli/" -ForegroundColor Red
    exit 1
}

# Check SAM CLI
if (Test-Command "sam") {
    $samVersion = sam --version
    Write-Host "[OK] SAM CLI installed: $samVersion" -ForegroundColor Green
} else {
    Write-Host "[ERROR] SAM CLI not found. Please install from: https://docs.aws.amazon.com/serverless-application-model/" -ForegroundColor Red
    exit 1
}

# Check AWS credentials
Write-Host "Checking AWS credentials..." -ForegroundColor Yellow
try {
    $identity = aws sts get-caller-identity --region $Region | ConvertFrom-Json
    Write-Host "[OK] AWS Account: $($identity.Account)" -ForegroundColor Green
    Write-Host "     User/Role: $($identity.Arn)" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] AWS credentials not configured. Run: aws configure" -ForegroundColor Red
    exit 1
}

# Check if Bedrock is enabled
Write-Host ""
Write-Host "CHECKING BEDROCK..." -ForegroundColor Cyan
$bedrockModels = aws bedrock list-foundation-models --region $Region --query "modelSummaries[?contains(modelId, 'claude')]" 2>$null

if ($bedrockModels -and $bedrockModels -like "*claude*") {
    Write-Host "[OK] Bedrock Claude models available" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Bedrock Claude might not be enabled" -ForegroundColor Yellow
    Write-Host "         Enable at: https://console.aws.amazon.com/bedrock/" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne 'y') {
        exit 1
    }
}

# Build SAM application
Write-Host ""
Write-Host "BUILDING SAM APPLICATION..." -ForegroundColor Cyan
sam build --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] SAM build failed" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] SAM build completed" -ForegroundColor Green

# Deploy SAM application
Write-Host ""
Write-Host "DEPLOYING TO AWS..." -ForegroundColor Cyan

$deployParams = @(
    "deploy",
    "--stack-name", $StackName,
    "--region", $Region,
    "--capabilities", "CAPABILITY_IAM",
    "--parameter-overrides", "BedrockModelId=anthropic.claude-3-opus-20240229",
    "--no-fail-on-empty-changeset"
)

# Check if samconfig.toml exists
if (Test-Path "samconfig.toml") {
    Write-Host "Using existing samconfig.toml" -ForegroundColor Gray
    sam @deployParams
} else {
    Write-Host "First deployment - using guided mode" -ForegroundColor Yellow
    sam deploy --guided
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] SAM deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Stack deployed successfully" -ForegroundColor Green

# Get stack outputs
Write-Host ""
Write-Host "RETRIEVING STACK OUTPUTS..." -ForegroundColor Cyan

$outputs = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --region $Region `
    --query "Stacks[0].Outputs" | ConvertFrom-Json

$apiUrl = ($outputs | Where-Object {$_.OutputKey -eq "ApiEndpoint"}).OutputValue
$websiteUrl = ($outputs | Where-Object {$_.OutputKey -eq "WebsiteURL"}).OutputValue
$websiteBucket = ($outputs | Where-Object {$_.OutputKey -eq "DocumentsBucketName"}).OutputValue

Write-Host "API Endpoint: $apiUrl" -ForegroundColor Green
Write-Host "Website URL: $websiteUrl" -ForegroundColor Green

# Update frontend with API URL
Write-Host ""
Write-Host "UPDATING FRONTEND..." -ForegroundColor Cyan

$indexPath = "frontend\index.html"
if (Test-Path $indexPath) {
    $content = Get-Content $indexPath -Raw
    $content = $content -replace 'https://your-api-gateway-url.execute-api.region.amazonaws.com/prod', $apiUrl
    Set-Content $indexPath $content
    Write-Host "[OK] Frontend updated with API URL" -ForegroundColor Green
    
    # Upload to S3
    Write-Host "Uploading frontend to S3..." -ForegroundColor Yellow
    aws s3 cp $indexPath "s3://$websiteBucket/" --region $Region
    Write-Host "[OK] Frontend uploaded" -ForegroundColor Green
}

# Update SSM Parameters with prompts
Write-Host ""
Write-Host "UPLOADING PROMPTS..." -ForegroundColor Cyan

$promptsPath = ".."
$promptA = "$promptsPath\CONTRAGARANTIAS.txt"
$promptB = "$promptsPath\INFORMES SOCIALES.txt"

if (Test-Path $promptA) {
    Write-Host "Uploading Agent A prompt..." -ForegroundColor Yellow
    $contentA = Get-Content $promptA -Raw
    aws ssm put-parameter `
        --name "/aspor/prompts/agent-a-contragarantias" `
        --value $contentA `
        --type "String" `
        --overwrite `
        --region $Region 2>$null
    Write-Host "[OK] Agent A prompt uploaded" -ForegroundColor Green
}

if (Test-Path $promptB) {
    Write-Host "Uploading Agent B prompt..." -ForegroundColor Yellow
    $contentB = Get-Content $promptB -Raw
    aws ssm put-parameter `
        --name "/aspor/prompts/agent-b-informes" `
        --value $contentB `
        --type "String" `
        --overwrite `
        --region $Region 2>$null
    Write-Host "[OK] Agent B prompt uploaded" -ForegroundColor Green
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "        DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Endpoint:" -ForegroundColor Yellow
Write-Host "  $apiUrl" -ForegroundColor White
Write-Host ""
Write-Host "Website URL:" -ForegroundColor Yellow
Write-Host "  $websiteUrl" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Test the API using Postman collection" -ForegroundColor White
Write-Host "  2. Access the web interface at the URL above" -ForegroundColor White
Write-Host "  3. Upload a test document and process it" -ForegroundColor White
Write-Host ""
Write-Host "To delete the stack later:" -ForegroundColor Yellow
Write-Host "  aws cloudformation delete-stack --stack-name $StackName --region $Region" -ForegroundColor White
Write-Host ""