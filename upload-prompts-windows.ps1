# Script para cargar prompts ASPOR a AWS SSM Parameter Store

$Region = "us-east-1"

Write-Host "Cargando prompts ASPOR a SSM Parameter Store..." -ForegroundColor Cyan

# Leer Prompt A - Contragarantías
$promptAPath = "CONTRAGARANTIAS.txt"
if (Test-Path $promptAPath) {
    Write-Host "Cargando Modelo A - Contragarantías..." -ForegroundColor Yellow
    $promptA = Get-Content $promptAPath -Raw -Encoding UTF8
    
    aws ssm put-parameter `
        --name "/aspor/prompts/agent-a-contragarantias" `
        --value "$promptA" `
        --type "String" `
        --overwrite `
        --region $Region `
        --no-cli-pager 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Prompt A cargado exitosamente" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] No se pudo cargar Prompt A" -ForegroundColor Red
    }
} else {
    Write-Host "[ERROR] No se encontró archivo CONTRAGARANTIAS.txt" -ForegroundColor Red
}

# Leer Prompt B - Informes Sociales
$promptBPath = "INFORMES SOCIALES.txt"
if (Test-Path $promptBPath) {
    Write-Host "Cargando Modelo B - Informes Sociales..." -ForegroundColor Yellow
    $promptB = Get-Content $promptBPath -Raw -Encoding UTF8
    
    aws ssm put-parameter `
        --name "/aspor/prompts/agent-b-informes" `
        --value "$promptB" `
        --type "String" `
        --overwrite `
        --region $Region `
        --no-cli-pager 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Prompt B cargado exitosamente" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] No se pudo cargar Prompt B" -ForegroundColor Red
    }
} else {
    Write-Host "[ERROR] No se encontró archivo INFORMES SOCIALES.txt" -ForegroundColor Red
}

Write-Host ""
Write-Host "Verificando prompts cargados..." -ForegroundColor Cyan

# Verificar Prompt A
$paramA = aws ssm get-parameter --name "/aspor/prompts/agent-a-contragarantias" --region $Region --query "Parameter.Value" --output text 2>$null
if ($paramA) {
    $sizeA = $paramA.Length
    Write-Host "[OK] Prompt A verificado - $sizeA caracteres" -ForegroundColor Green
}

# Verificar Prompt B
$paramB = aws ssm get-parameter --name "/aspor/prompts/agent-b-informes" --region $Region --query "Parameter.Value" --output text 2>$null
if ($paramB) {
    $sizeB = $paramB.Length
    Write-Host "[OK] Prompt B verificado - $sizeB caracteres" -ForegroundColor Green
}

Write-Host ""
Write-Host "Prompts cargados exitosamente!" -ForegroundColor Green