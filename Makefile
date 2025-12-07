.PHONY: up down logs test clean restart shell

# Start the application (build and run in detached mode)
up:
	docker compose up -d --build

# Stop and remove containers, networks, and volumes
down:
	docker compose down -v

# View logs from the api service (follow mode)
logs:
	docker compose logs -f api

# Run tests inside the container
test:
	docker compose run --rm api pytest

# Restart the application
restart: down up

# Open a shell in the running container
shell:
	docker compose exec api /bin/bash

# Clean up everything (containers, volumes, images)
clean:
	docker compose down -v --rmi all

# Check application health
health:
	@echo "Checking application health..."
	@curl -f http://localhost:8000/health/ready || echo "Application not ready"

# View metrics
metrics:
	@curl http://localhost:8000/metrics

# Help command
help:
	@echo "Available commands:"
	@echo "  make up       - Build and start the application"
	@echo "  make down     - Stop and remove containers"
	@echo "  make logs     - View application logs"
	@echo "  make test     - Run tests"
	@echo "  make restart  - Restart the application"
	@echo "  make shell    - Open shell in container"
	@echo "  make clean    - Remove all containers, volumes, and images"
	@echo "  make health   - Check application health"
	@echo "  make metrics  - View Prometheus metrics"
