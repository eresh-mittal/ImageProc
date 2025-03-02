# app.py - Main FastAPI application
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import os
from models import Request, Product, get_db, Base, engine
from celery import Celery
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import datetime
import shutil

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Image Processor API")

# Configure environment constants
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'csv'}

# Configure Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery = Celery("tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# Create database tables
Base.metadata.create_all(bind=engine)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    csvFile: UploadFile = File(...),
    webhookUrl: Optional[str] = Form(None)
):
    if not csvFile.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    
    if not allowed_file(csvFile.filename):
        raise HTTPException(status_code=400, detail="Invalid file format")

    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    db = get_db().__next__()
    
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    
    # Save the CSV file
    filename = secure_filename(csvFile.filename)
    file_path = os.path.join(UPLOAD_FOLDER, f"{request_id}_{filename}")
    
    # Save the uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(csvFile.file, buffer)
    
    # Create a new request in the database
    new_request = Request(
        request_id=request_id,
        status='PENDING',
        webhook_url=webhookUrl,
        csv_file_path=file_path,
        created_at=datetime.now()
    )
    db.add(new_request)
    db.commit()
    
    # Queue the CSV processing task
    from tasks import process_csv
    print("before celery")
    celery.send_task("tasks.process_csv", args=[request_id, file_path, webhookUrl])
    
    return JSONResponse(
        status_code=202,
        content={
            'message': 'CSV file accepted for processing',
            'requestId': request_id
        }
    )

@app.get("/api/status/{request_id}")
async def check_status(request_id: str):
    # Find the request in the database
    db = (get_db()).__next__()
    processing_request = db.query(Request).filter(Request.request_id == request_id).first()
    
    if not processing_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Count processed products
    products_count = db.query(Product).filter(Product.request_id == request_id).count()
    
    return {
        'requestId': processing_request.request_id,
        'status': processing_request.status,
        'progress': processing_request.progress,
        'createdAt': processing_request.created_at.isoformat(),
        'completedAt': processing_request.completed_at.isoformat() if processing_request.completed_at else None,
        'productsProcessed': products_count,
        'outputCsvUrl': processing_request.output_csv_url
    }

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)