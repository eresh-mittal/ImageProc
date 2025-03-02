# Image Processing System Technical Documentation

## System Overview

The Image Processing System is designed to process large batches of product images based on information provided in CSV files. It uses a microservices architecture with FastAPI, Celery, PostgreSQL, and Redis to provide a scalable, non-blocking solution for image processing tasks.

## Architecture Components

### 1. FastAPI Application (app.py)

The FastAPI application serves as the API layer for the system, handling:

- File uploads via the `/api/upload` endpoint
- Status checks via the `/api/status/{request_id}` endpoint
- Database interactions for storing and retrieving request metadata
- Task dispatching to the Celery queue

FastAPI was chosen for its high performance, automatic OpenAPI documentation, and native async support.

### 2. Celery Worker (tasks.py)

The Celery worker handles background processing tasks:

- CSV file parsing and validation
- Image processing for each product
- Status updates to the database
- Optional webhook notifications when processing completes

Celery enables asynchronous processing of potentially time-consuming tasks without blocking the API.

### 3. PostgreSQL Database (models.py)

PostgreSQL stores structured data including:

- Request metadata (status, progress, file paths)
- Product information (product IDs, image URLs, processing status)

The system uses SQLAlchemy for ORM functionality and database interactions.

### 4. Redis

Redis serves as:

- A message broker for Celery tasks
- A result backend for storing task statuses

### 5. File System

Local file system storage is used for:

- Temporarily storing uploaded CSV files
- Storing processed output files

## Data Flow

1. **Upload Phase:**
   - Client uploads a CSV file to the `/api/upload` endpoint
   - FastAPI validates the file and creates a request record in PostgreSQL
   - The task is queued in Redis and a request ID is returned to the client

2. **Processing Phase:**
   - Celery worker retrieves the task from Redis
   - Worker reads the CSV and processes each product entry
   - Database is updated with progress information
   - Processed results are saved to the file system

3. **Completion Phase:**
   - Output CSV with processing results is generated
   - Request status is updated to "COMPLETED"
   - Optional webhook notification is sent if configured
   - Client can access results via the status endpoint

## Deployment

The system is containerized using Docker, with separate containers for:

- FastAPI application
- Celery workers
- PostgreSQL database
- Redis

Docker Compose is used for local development and testing, with orchestration via Kubernetes recommended for production environments.

## Scaling Considerations

The architecture supports horizontal scaling through:

- Stateless API servers that can be replicated
- Multiple Celery workers processing tasks in parallel
- Redis and PostgreSQL can be configured for high availability

## Security Considerations

- File validation prevents malicious uploads
- Database connections use parameterized queries to prevent SQL injection
- Authentication and authorization should be implemented before production deployment

## Future Enhancements

1. Cloud Storage Integration:
   - AWS S3 for durable file storage
   - Presigned URLs for secure file access

2. Enhanced Monitoring:
   - Prometheus metrics for system performance
   - Grafana dashboards for visualization

3. Additional Features:
   - Batch processing priorities
   - Advanced image processing options
   - User management and access controls
