@echo off
echo Cargando prompts a SSM Parameter Store...

echo Cargando Prompt A...
type CONTRAGARANTIAS.txt | aws ssm put-parameter --name "/aspor/prompts/agent-a-contragarantias" --value file:///dev/stdin --type String --overwrite --region us-east-1 --cli-input-json "{}" 2>nul

echo Cargando Prompt B...
type "INFORMES SOCIALES.txt" | aws ssm put-parameter --name "/aspor/prompts/agent-b-informes" --value file:///dev/stdin --type String --overwrite --region us-east-1 --cli-input-json "{}" 2>nul

echo Prompts cargados.
echo.
echo Verificando...
aws ssm get-parameter --name "/aspor/prompts/agent-a-contragarantias" --region us-east-1 --query "Parameter.Value" --output text 2>nul | findstr /c:"Eres un asistente" >nul
if %ERRORLEVEL%==0 (
    echo Prompt A: OK
) else (
    echo Prompt A: ERROR
)

aws ssm get-parameter --name "/aspor/prompts/agent-b-informes" --region us-east-1 --query "Parameter.Value" --output text 2>nul | findstr /c:"Eres un asistente" >nul
if %ERRORLEVEL%==0 (
    echo Prompt B: OK
) else (
    echo Prompt B: ERROR
)