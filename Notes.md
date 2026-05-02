




View Logs:
**********
	# Specific service
	docker compose logs -f web
	docker compose logs -f celery-worker
	docker compose logs -f celery-beat
	docker compose logs -f postgres

	# All services
	docker compose logs -f

Access the application:
************************

	API: http://localhost:8000/api/
	Swagger UI: http://localhost:8000/api/docs/
	ReDoc: http://localhost:8000/api/redoc/
	Health: http://localhost:8000/api/health/

Port Information:
*****************
	PostgreSQL (port 5432)
	Redis (port 6379)
	Django Web (port 8000)
	Celery Worker
	Celery Beat (scheduler)



