# ASPOR Extraction Platform - Makefile

.PHONY: help install build deploy clean test local update-prompts

STACK_NAME ?= aspor-extraction-platform
REGION ?= us-east-1
PYTHON = python3.12

help: ## Show this help message
	@echo "ASPOR Extraction Platform - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt
	pip install aws-sam-cli boto3

build: ## Build SAM application
	sam build --region $(REGION)

deploy: build ## Deploy to AWS
	./deploy.sh $(STACK_NAME) $(REGION)

clean: ## Clean build artifacts
	rm -rf .aws-sam
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test: ## Run unit tests
	$(PYTHON) -m pytest tests/ -v

local: ## Start local API for testing
	sam local start-api --region $(REGION)

update-prompts: ## Update prompts in SSM Parameter Store
	@echo "Updating Agent A prompt..."
	@aws ssm put-parameter \
		--name "/aspor/prompts/agent-a-contragarantias" \
		--value "$$(cat ../../CONTRAGARANTIAS.txt)" \
		--type "String" \
		--overwrite \
		--region $(REGION)
	@echo "Updating Agent B prompt..."
	@aws ssm put-parameter \
		--name "/aspor/prompts/agent-b-informes" \
		--value "$$(cat ../../'INFORMES SOCIALES.txt')" \
		--type "String" \
		--overwrite \
		--region $(REGION)
	@echo "Prompts updated successfully!"

validate: ## Validate SAM template
	sam validate --region $(REGION)

logs: ## Tail CloudWatch logs for all functions
	sam logs --stack-name $(STACK_NAME) --tail --region $(REGION)

destroy: ## Delete the stack and all resources
	@echo "WARNING: This will delete all resources including data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	aws cloudformation delete-stack --stack-name $(STACK_NAME) --region $(REGION)
	@echo "Stack deletion initiated. Check AWS Console for status."

status: ## Check stack status
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query "Stacks[0].StackStatus" \
		--output text

outputs: ## Show stack outputs
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query "Stacks[0].Outputs" \
		--output table