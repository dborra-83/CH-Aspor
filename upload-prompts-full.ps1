# Script para cargar los prompts completos desde los archivos TXT a AWS SSM
$Region = "us-east-1"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Cargando prompts completos a AWS SSM" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Función para cargar prompt a SSM
function Upload-Prompt {
    param(
        [string]$FilePath,
        [string]$ParameterName,
        [string]$ModelName
    )
    
    Write-Host "Procesando $ModelName..." -ForegroundColor Yellow
    
    if (Test-Path $FilePath) {
        # Leer archivo completo
        $content = Get-Content $FilePath -Raw -Encoding UTF8
        $size = $content.Length
        
        Write-Host "  - Archivo encontrado: $FilePath" -ForegroundColor Gray
        Write-Host "  - Tamaño: $size caracteres" -ForegroundColor Gray
        
        # Verificar tamaño (SSM tiene límite de 4KB para String, 8KB para SecureString)
        if ($size -gt 4000) {
            Write-Host "  - Usando SecureString por tamaño grande" -ForegroundColor Yellow
            $type = "SecureString"
        } else {
            $type = "String"
        }
        
        # Cargar a SSM
        Write-Host "  - Cargando a SSM..." -ForegroundColor Gray
        
        # Crear archivo temporal para evitar problemas con caracteres especiales
        $tempFile = [System.IO.Path]::GetTempFileName()
        Set-Content -Path $tempFile -Value $content -Encoding UTF8 -NoNewline
        
        $result = aws ssm put-parameter `
            --name $ParameterName `
            --value file://$tempFile `
            --type $type `
            --overwrite `
            --region $Region `
            --description "$ModelName prompt para ASPOR" `
            2>&1
        
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $ModelName cargado exitosamente" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  ✗ Error al cargar $ModelName" -ForegroundColor Red
            Write-Host "    $result" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "  ✗ Archivo no encontrado: $FilePath" -ForegroundColor Red
        return $false
    }
}

# Cargar Prompt A - Contragarantías
$promptALoaded = Upload-Prompt `
    -FilePath "CONTRAGARANTIAS.txt" `
    -ParameterName "/aspor/prompts/agent-a-contragarantias" `
    -ModelName "Modelo A - Contragarantías"

Write-Host ""

# Cargar Prompt B - Informes Sociales
$promptBLoaded = Upload-Prompt `
    -FilePath "INFORMES SOCIALES.txt" `
    -ParameterName "/aspor/prompts/agent-b-informes" `
    -ModelName "Modelo B - Informes Sociales"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Verificando prompts cargados..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Prompt A
Write-Host "Verificando Modelo A..." -ForegroundColor Yellow
$paramA = aws ssm get-parameter `
    --name "/aspor/prompts/agent-a-contragarantias" `
    --region $Region `
    --query "Parameter.Value" `
    --output text `
    2>$null

if ($paramA) {
    $sizeA = $paramA.Length
    $preview = if ($sizeA -gt 100) { $paramA.Substring(0, 100) + "..." } else { $paramA }
    Write-Host "  ✓ Modelo A verificado" -ForegroundColor Green
    Write-Host "  - Tamaño: $sizeA caracteres" -ForegroundColor Gray
    Write-Host "  - Vista previa: $preview" -ForegroundColor Gray
} else {
    Write-Host "  ✗ No se pudo verificar Modelo A" -ForegroundColor Red
}

Write-Host ""

# Verificar Prompt B
Write-Host "Verificando Modelo B..." -ForegroundColor Yellow
$paramB = aws ssm get-parameter `
    --name "/aspor/prompts/agent-b-informes" `
    --region $Region `
    --query "Parameter.Value" `
    --output text `
    2>$null

if ($paramB) {
    $sizeB = $paramB.Length
    $preview = if ($sizeB -gt 100) { $paramB.Substring(0, 100) + "..." } else { $paramB }
    Write-Host "  ✓ Modelo B verificado" -ForegroundColor Green
    Write-Host "  - Tamaño: $sizeB caracteres" -ForegroundColor Gray
    Write-Host "  - Vista previa: $preview" -ForegroundColor Gray
} else {
    Write-Host "  ✗ No se pudo verificar Modelo B" -ForegroundColor Red
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan

if ($promptALoaded -and $promptBLoaded) {
    Write-Host "✓ Prompts cargados exitosamente!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Los prompts están listos para usar en:" -ForegroundColor Gray
    Write-Host "  - /aspor/prompts/agent-a-contragarantias" -ForegroundColor White
    Write-Host "  - /aspor/prompts/agent-b-informes" -ForegroundColor White
} else {
    Write-Host "✗ Hubo errores al cargar los prompts" -ForegroundColor Red
    Write-Host "Por favor revise los mensajes de error arriba" -ForegroundColor Yellow
}

Write-Host "=====================================" -ForegroundColor Cyan