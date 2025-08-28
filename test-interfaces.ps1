# Test script for ASPOR interfaces
Write-Host "Testing ASPOR Platform Interfaces" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

$apiUrl = "https://bsdxo3p5tc.execute-api.us-east-1.amazonaws.com/prod"
$cloudfrontUrl = "https://d3qiqro0ukto58.cloudfront.net"

# Test 1: Check API endpoints
Write-Host "`n1. Testing API Endpoints:" -ForegroundColor Yellow

# Test presign endpoint
Write-Host "   Testing /runs/presign endpoint..."
$presignBody = @{
    file_count = 1
} | ConvertTo-Json

try {
    $presignResponse = Invoke-RestMethod -Uri "$apiUrl/runs/presign" -Method POST -Body $presignBody -ContentType "application/json"
    Write-Host "   OK - Presign endpoint working" -ForegroundColor Green
    Write-Host "     Method: $($presignResponse.uploads[0].method)" -ForegroundColor Gray
    $urlPreview = $presignResponse.uploads[0].url.Substring(0, [Math]::Min(50, $presignResponse.uploads[0].url.Length))
    Write-Host "     URL starts with: $urlPreview..." -ForegroundColor Gray
} catch {
    Write-Host "   ERROR - Presign endpoint failed: $_" -ForegroundColor Red
}

# Test 2: Check CloudFront access
Write-Host "`n2. Testing CloudFront Access:" -ForegroundColor Yellow

$interfaces = @(
    @{name="Classic Interface"; path="/index.html"},
    @{name="Chat Interface"; path="/chat.html"}
)

foreach ($interface in $interfaces) {
    Write-Host "   Testing $($interface.name)..."
    try {
        $response = Invoke-WebRequest -Uri "$cloudfrontUrl$($interface.path)" -Method HEAD
        if ($response.StatusCode -eq 200) {
            Write-Host "   OK - $($interface.name) accessible" -ForegroundColor Green
        }
    } catch {
        Write-Host "   ERROR - $($interface.name) not accessible: $_" -ForegroundColor Red
    }
}

# Test 3: Verify Lambda functions
Write-Host "`n3. Verifying Lambda Functions:" -ForegroundColor Yellow

$lambdaFunctions = @(
    "aspor-create-run",
    "aspor-presign",
    "aspor-get-run",
    "aspor-list-runs"
)

foreach ($function in $lambdaFunctions) {
    try {
        $lambdaInfo = aws lambda get-function --function-name $function --region us-east-1 --query "Configuration.[State,LastModified]" --output json | ConvertFrom-Json
        $state = $lambdaInfo[0]
        $lastMod = $lambdaInfo[1].Substring(0,10)
        Write-Host "   OK - ${function}: $state (Updated: $lastMod)" -ForegroundColor Green
    } catch {
        Write-Host "   ERROR - ${function}: Error checking function" -ForegroundColor Red
    }
}

Write-Host "`n4. Summary:" -ForegroundColor Yellow
Write-Host "   API Endpoint: $apiUrl" -ForegroundColor Cyan
Write-Host "   Classic Interface: $cloudfrontUrl/index.html" -ForegroundColor Cyan
Write-Host "   Chat Interface: $cloudfrontUrl/chat.html" -ForegroundColor Cyan

Write-Host "`nAll systems should be operational!" -ForegroundColor Green
Write-Host "Please test file upload and processing in both interfaces to confirm." -ForegroundColor Yellow