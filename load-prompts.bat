@echo off
echo =====================================
echo Cargando prompts completos a AWS SSM
echo =====================================
echo.

echo Cargando Modelo A - Contragarantias...
aws ssm put-parameter --name "/aspor/prompts/agent-a-contragarantias" --value file://CONTRAGARANTIAS.txt --type String --overwrite --region us-east-1 --description "Modelo A Contragarantias ASPOR" >nul 2>&1

if %ERRORLEVEL%==0 (
    echo [OK] Modelo A cargado
) else (
    echo [ERROR] No se pudo cargar Modelo A - intentando con SecureString...
    aws ssm delete-parameter --name "/aspor/prompts/agent-a-contragarantias" --region us-east-1 >nul 2>&1
    aws ssm put-parameter --name "/aspor/prompts/agent-a-contragarantias" --value file://CONTRAGARANTIAS.txt --type SecureString --overwrite --region us-east-1 --description "Modelo A Contragarantias ASPOR" >nul 2>&1
    if %ERRORLEVEL%==0 (
        echo [OK] Modelo A cargado como SecureString
    ) else (
        echo [ERROR] No se pudo cargar Modelo A
    )
)

echo.
echo Cargando Modelo B - Informes Sociales...
aws ssm put-parameter --name "/aspor/prompts/agent-b-informes" --value file://"INFORMES SOCIALES.txt" --type String --overwrite --region us-east-1 --description "Modelo B Informes Sociales ASPOR" >nul 2>&1

if %ERRORLEVEL%==0 (
    echo [OK] Modelo B cargado
) else (
    echo [ERROR] No se pudo cargar Modelo B - intentando con SecureString...
    aws ssm delete-parameter --name "/aspor/prompts/agent-b-informes" --region us-east-1 >nul 2>&1
    aws ssm put-parameter --name "/aspor/prompts/agent-b-informes" --value file://"INFORMES SOCIALES.txt" --type SecureString --overwrite --region us-east-1 --description "Modelo B Informes Sociales ASPOR" >nul 2>&1
    if %ERRORLEVEL%==0 (
        echo [OK] Modelo B cargado como SecureString
    ) else (
        echo [ERROR] No se pudo cargar Modelo B
    )
)

echo.
echo =====================================
echo Verificando prompts cargados...
echo =====================================
echo.

echo Verificando Modelo A...
for /f "tokens=*" %%i in ('aws ssm get-parameter --name "/aspor/prompts/agent-a-contragarantias" --region us-east-1 --query "Parameter.Type" --output text 2^>nul') do set TYPE_A=%%i
for /f "tokens=*" %%i in ('aws ssm get-parameter --name "/aspor/prompts/agent-a-contragarantias" --region us-east-1 --with-decryption --query "Parameter.Value" --output text 2^>nul ^| find /c /v ""') do set LINES_A=%%i

if defined TYPE_A (
    echo [OK] Modelo A - Tipo: %TYPE_A% - Lineas: %LINES_A%
) else (
    echo [ERROR] Modelo A no encontrado
)

echo.
echo Verificando Modelo B...
for /f "tokens=*" %%i in ('aws ssm get-parameter --name "/aspor/prompts/agent-b-informes" --region us-east-1 --query "Parameter.Type" --output text 2^>nul') do set TYPE_B=%%i
for /f "tokens=*" %%i in ('aws ssm get-parameter --name "/aspor/prompts/agent-b-informes" --region us-east-1 --with-decryption --query "Parameter.Value" --output text 2^>nul ^| find /c /v ""') do set LINES_B=%%i

if defined TYPE_B (
    echo [OK] Modelo B - Tipo: %TYPE_B% - Lineas: %LINES_B%
) else (
    echo [ERROR] Modelo B no encontrado
)

echo.
echo =====================================
echo Proceso completado
echo =====================================
pause