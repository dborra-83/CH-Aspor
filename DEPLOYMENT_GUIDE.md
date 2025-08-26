# 📚 GUÍA COMPLETA DE DESPLIEGUE - CH-ASPOR

Esta guía te llevará paso a paso desde cero hasta tener la aplicación funcionando en AWS.

---

## 📋 PREREQUISITOS

### 1. Instalar Herramientas Necesarias

#### AWS CLI
```powershell
# Opción 1: Usando MSI Installer (Windows)
# Descargar desde: https://aws.amazon.com/cli/
# O usar comando:
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# Verificar instalación
aws --version
```

#### SAM CLI
```powershell
# Descargar instalador desde:
# https://github.com/aws/aws-sam-cli/releases/latest/download/AWS_SAM_CLI_64_PPC.msi

# O usando pip (si tienes Python)
pip install aws-sam-cli

# Verificar instalación  
sam --version
```

#### Python 3.12
```powershell
# Descargar desde: https://www.python.org/downloads/
# Asegúrate de marcar "Add Python to PATH" durante instalación

# Verificar
python --version
```

---

## 🔑 PASO 1: CONFIGURAR CUENTA AWS

### 1.1 Crear Cuenta AWS (si no tienes)
1. Ve a https://aws.amazon.com
2. Click en "Create an AWS Account"
3. Completa el registro (necesitarás tarjeta de crédito)

### 1.2 Crear Usuario IAM para Despliegue
```bash
# Desde la consola AWS:
# 1. IAM → Users → Add User
# 2. Nombre: aspor-deployer
# 3. Attach policies:
#    - AdministratorAccess (para simplificar, luego puedes restringir)
# 4. Security credentials → Create access key
# 5. Guarda las credenciales
```

### 1.3 Configurar AWS CLI
```bash
aws configure

# Te pedirá:
AWS Access Key ID [None]: TU_ACCESS_KEY_ID
AWS Secret Access Key [None]: TU_SECRET_ACCESS_KEY
Default region name [None]: us-east-1
Default output format [None]: json
```

### 1.4 Verificar Configuración
```bash
aws sts get-caller-identity
# Debe mostrar tu cuenta y usuario
```

---

## 🤖 PASO 2: HABILITAR BEDROCK CLAUDE

### 2.1 Acceder a Bedrock
1. Ingresa a AWS Console: https://console.aws.amazon.com
2. Busca "Bedrock" en la barra de búsqueda
3. Selecciona la región **us-east-1** (N. Virginia)

### 2.2 Habilitar Modelo Claude
1. En Bedrock, ve a **"Model access"** en el menú izquierdo
2. Click en **"Manage model access"**
3. Busca **"Claude"** en la lista
4. Selecciona:
   - ✅ Claude 3 Opus
   - ✅ Claude 3 Sonnet (opcional)
5. Click **"Request model access"**
6. Completa el formulario (uso: Development/Testing)
7. Click **"Submit"**

⏰ **Nota**: La aprobación puede tardar 1-5 minutos. Refresca la página para ver el estado.

### 2.3 Verificar Acceso
```bash
aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude')]"
# Debe listar los modelos Claude disponibles
```

---

## 🚀 PASO 3: DESPLEGAR LA APLICACIÓN

### 3.1 Clonar el Repositorio
```bash
# Si acabas de subirlo a GitHub:
git clone https://github.com/dborra-83/CH-Aspor.git
cd CH-Aspor/aspor-extraction-platform

# O si ya lo tienes local:
cd C:/FILESERVER/CLOUDHESIVE/TEST3/CH-Aspor/aspor-extraction-platform
```

### 3.2 Instalar Dependencias Python
```bash
# Crear entorno virtual (opcional pero recomendado)
python -m venv venv

# Activar entorno (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
pip install boto3 aws-sam-cli
```

### 3.3 Ejecutar Script de Despliegue

#### Opción A: Usando el script bash (Git Bash requerido)
```bash
# Dar permisos de ejecución
chmod +x deploy.sh

# Ejecutar
./deploy.sh aspor-platform us-east-1
```

#### Opción B: Usando SAM directamente
```bash
# Build
sam build

# Deploy (primera vez)
sam deploy --guided

# Te preguntará:
Stack Name [sam-app]: aspor-platform
AWS Region [us-east-1]: us-east-1
Parameter BedrockModelId []: anthropic.claude-3-opus-20240229
Confirm changes before deploy [y/N]: N
Allow SAM CLI IAM role creation [Y/n]: Y
Disable rollback [y/N]: N
Save parameters to configuration file [Y/n]: Y
SAM configuration file [samconfig.toml]: samconfig.toml
SAM configuration environment [default]: default
```

### 3.4 Esperar Despliegue
El proceso tardará aproximadamente 5-10 minutos. Verás algo como:
```
CloudFormation stack changeset
---------------------------------
Operation  LogicalResourceId                     ResourceType
+ Add      AsporApi                             AWS::ApiGateway::RestApi
+ Add      DocumentsBucket                      AWS::S3::Bucket
+ Add      ExtractionsTable                     AWS::DynamoDB::Table
+ Add      CreateRunFunction                    AWS::Lambda::Function
...

Successfully created/updated stack - aspor-platform
```

---

## 📝 PASO 4: CONFIGURAR PROMPTS

### 4.1 Subir Prompts a SSM Parameter Store
```bash
# Desde la carpeta raíz del proyecto
cd C:/FILESERVER/CLOUDHESIVE/TEST3/CH-Aspor

# Ejecutar script Python
python aspor-extraction-platform/upload_prompts.py --region us-east-1
```

### 4.2 Verificar Prompts
```bash
# Verificar que se subieron correctamente
aws ssm get-parameter --name "/aspor/prompts/agent-a-contragarantias" --region us-east-1 --query "Parameter.Value" --output text | head -20
```

---

## 🌐 PASO 5: CONFIGURAR FRONTEND

### 5.1 Obtener URLs del Stack
```bash
# Obtener URL del API
aws cloudformation describe-stacks \
  --stack-name aspor-platform \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text

# Obtener bucket del website
aws cloudformation describe-stacks \
  --stack-name aspor-platform \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
  --output text
```

### 5.2 Actualizar y Subir Frontend
```bash
# Actualizar el HTML con la URL del API
$API_URL = "https://xxxxx.execute-api.us-east-1.amazonaws.com/prod"
$WEBSITE_BUCKET = "aspor-website-xxxxx"

# En PowerShell:
(Get-Content frontend/index.html) -replace 'https://your-api-gateway-url.execute-api.region.amazonaws.com/prod', $API_URL | Set-Content frontend/index.html

# Subir a S3
aws s3 cp frontend/index.html s3://$WEBSITE_BUCKET/ --region us-east-1
```

### 5.3 Obtener URL del Website
```bash
aws cloudformation describe-stacks \
  --stack-name aspor-platform \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" \
  --output text
```

---

## ✅ PASO 6: VERIFICAR Y PROBAR

### 6.1 Verificar Recursos Creados
```bash
# Verificar Lambda functions
aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'aspor')].[FunctionName]" --output table

# Verificar DynamoDB
aws dynamodb list-tables --query "TableNames[?contains(@, 'aspor')]" --output table

# Verificar S3 buckets
aws s3 ls | grep aspor
```

### 6.2 Probar con Postman
1. Importa `postman_collection.json`
2. Actualiza la variable `base_url` con tu API URL
3. Ejecuta las pruebas en orden

### 6.3 Probar Interfaz Web
1. Abre la URL del website en tu navegador
2. Sube un archivo PDF o DOCX de prueba
3. Selecciona Modelo A o B
4. Procesa y descarga el resultado

---

## 🔧 TROUBLESHOOTING

### Error: "Bedrock model not found"
```bash
# Verificar que el modelo esté habilitado
aws bedrock get-foundation-model \
  --model-identifier anthropic.claude-3-opus-20240229 \
  --region us-east-1
```

### Error: "Access Denied"
```bash
# Verificar rol de Lambda
aws iam get-role --role-name aspor-platform-CreateRunFunctionRole-xxxx
```

### Error: "Timeout"
- Aumenta el timeout en template.yaml (línea Timeout: 900)
- Redespliega: `sam deploy`

### Ver Logs
```bash
# Ver logs de una función
sam logs -n CreateRunFunction --stack-name aspor-platform --tail

# O desde CloudWatch
aws logs tail /aws/lambda/aspor-create-run --follow
```

---

## 💰 MONITOREAR COSTOS

```bash
# Ver costos del mes actual
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query "ResultsByTime[].Groups[].[Keys[0],Metrics.UnblendedCost.Amount]" \
  --output table
```

---

## 🗑️ ELIMINAR RECURSOS (Cuando termines)

```bash
# Eliminar stack completo
aws cloudformation delete-stack --stack-name aspor-platform --region us-east-1

# Verificar eliminación
aws cloudformation describe-stacks --stack-name aspor-platform --region us-east-1
```

---

## 📞 SOPORTE

Si tienes problemas:
1. Revisa los logs en CloudWatch
2. Verifica que Bedrock esté habilitado
3. Confirma que las credenciales AWS tengan permisos
4. Abre un issue en: https://github.com/dborra-83/CH-Aspor/issues

---

## ✅ CHECKLIST FINAL

- [ ] AWS CLI configurado y funcionando
- [ ] SAM CLI instalado
- [ ] Python 3.12 instalado
- [ ] Bedrock Claude habilitado en us-east-1
- [ ] Stack desplegado exitosamente
- [ ] Prompts cargados en SSM
- [ ] Frontend actualizado con API URL
- [ ] Primera prueba exitosa

¡Listo! Tu plataforma ASPOR está funcionando en AWS 🎉