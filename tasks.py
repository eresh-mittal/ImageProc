from celery import Celery
import os
import pandas as pd
import requests
from datetime import datetime, timezone
from models import Request, Product, SessionLocal, get_db
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import time

# Load environment variables
load_dotenv()

# Configure Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery = Celery("tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

@celery.task(name="tasks.process_csv")
def process_csv(request_id, file_path, webhook_url=None):
    """
    Process the uploaded CSV file, including image processing (resize to half).
    Handles multiple image URLs in a single cell and provides comprehensive logging.
    """
    print(f"Starting CSV processing for request_id: {request_id}, file_path: {file_path}")
    # Create a new session
    db = (get_db()).__next__()
    try:
        # Update the request status
        processing_request = db.query(Request).filter(Request.request_id == request_id).first()
        if not processing_request:
            print(f"Request with ID {request_id} not found in database")
            return
        
        processing_request.status = 'PROCESSING'
        db.commit()
        print(f"Updated request status to PROCESSING for request_id: {request_id}")
        
        # Read the CSV file
        print(f"Reading CSV file from: {file_path}")
        df = pd.read_csv(file_path)
        total_rows = len(df)
        print(f"Total rows to process: {total_rows}")
        
        # Ensure output folder exists
        output_folder = os.path.join("processed_images", request_id)
        os.makedirs(output_folder, exist_ok=True)
        print(f"Created output folder: {output_folder}")

        # Process each row in the CSV
        for index, row in df.iterrows():
            product_id = row.get('product_id')
            image_url_raw = row.get('image_url')
            print(f"Processing row {index+1}/{total_rows}, product_id: {product_id}")
            # Handle multiple URLs in a single cell
            if isinstance(image_url_raw, str):
                image_urls = [url.strip() for url in image_url_raw.split(",")]
            else:
                print(f"Invalid image_url format for product_id {product_id}: {image_url_raw}")
                image_urls = []
            
            print(f"Found {len(image_urls)} URLs for product_id {product_id}")
            
            # Create a product entry in the database
            product = Product(
                request_id=request_id,
                product_id=product_id,
                image_url=image_url_raw,  # Store the original raw string
                status='PENDING'
            )
            db.add(product)
            db.commit()
            print(f"Added product to database with status PENDING: {product_id}")
            
            # Process all URLs for this product
            processed_urls = []
            has_failures = False
            
            for idx, image_url in enumerate(image_urls):
                image_url = image_url.strip()
                if not image_url:
                    continue
                    
                print(f"Processing URL {idx+1}/{len(image_urls)} for product {product_id}: {image_url}")
                
                # Download and process the image
                try:
                    print(f"Downloading image from: {image_url}")
                    response = requests.get(image_url, timeout=30)
                
                    if response.status_code == 200:
                        # Open the image using Pillow
                        img = Image.open(BytesIO(response.content))
                        original_size = img.size
                        print(f"Original image size: {original_size}")
                        
                        # Resize the image to half
                        resized_img = img.resize((original_size[0] // 2, original_size[1] // 2))
                        
                        # Save the resized image locally
                        suffix = f"_{idx}" if len(image_urls) > 1 else ""
                        processed_image_path = os.path.join(output_folder, f"{product_id}{suffix}_resized.jpg")
                        resized_img.save(processed_image_path)
                        print(f"Saved resized image to: {processed_image_path}")
                        
                        # Add the processed URL to our list
                        processed_url = f"/processed_images/{request_id}/{product_id}{suffix}_resized.jpg"
                        processed_urls.append(processed_url)
                    else:
                        print(f"Failed to download image from {image_url}. Status code: {response.status_code}")
                        has_failures = True
                    
                except Exception as e:
                    print(f"Error processing image URL for product {product_id}: {e}")
                    has_failures = True
            
            # Update product status based on processing results
            if not processed_urls:
                product.status = 'FAILED'
                print(f"All image processing failed for product: {product_id}")
            elif has_failures:
                product.status = 'PARTIAL'
                print(f"Some image processing failed for product: {product_id}")
                product.processed_image_url = ",".join(processed_urls)
            else:
                product.status = 'COMPLETED'
                print(f"All image processing successful for product: {product_id}")
                product.processed_image_url = ",".join(processed_urls)
            
            # Commit the changes for each product
            db.commit()

            # Update progress
            progress = (index + 1) / total_rows * 100
            processing_request.progress = progress
            db.commit()
            print(f"Updated progress to {progress:.2f}% for request_id: {request_id}")

        # Generate output CSV
        output_path = f"outputs/{request_id}_output.csv"
        os.makedirs("outputs", exist_ok=True)
        print(f"Generating output CSV at: {output_path}")
        
        # Create a DataFrame with processed results
        products = db.query(Product).filter(Product.request_id == request_id).all()
        output_data = {
            'product_id': [p.product_id for p in products],
            'original_image_url': [p.image_url for p in products],
            'processed_image_url': [p.processed_image_url for p in products],
            'status': [p.status for p in products]
        }
        output_df = pd.DataFrame(output_data)
        output_df.to_csv(output_path, index=False)
        print(f"Output CSV generated successfully with {len(products)} products")
        
        # Update request status
        processing_request.status = 'COMPLETED'
        processing_request.completed_at = datetime.now(timezone.utc)
        processing_request.output_csv_url = f"/outputs/{request_id}_output.csv"
        db.commit()
        print(f"Updated request status to COMPLETED for request_id: {request_id}")
        
        # Call webhook if provided
        if webhook_url:
            try:
                print(f"Calling webhook URL: {webhook_url}")
                response = requests.post(webhook_url, json={
                    'requestId': request_id,
                    'status': 'COMPLETED',
                    'outputCsvUrl': processing_request.output_csv_url
                }, timeout=30)
                print(f"Webhook response status: {response.status_code}")
            except Exception as e:
                print(f"Error calling webhook: {e}")
                
    except Exception as e:
        # Update request status to failed
        print(f"Critical error in process_csv: {e}")
        try:
            processing_request = db.query(Request).filter(Request.request_id == request_id).first()
            if processing_request:
                processing_request.status = 'FAILED'
                db.commit()
                print(f"Updated request status to FAILED for request_id: {request_id}")
        except Exception as inner_e:
            print(f"Error updating request status to FAILED: {inner_e}")
        raise e
    
    finally:
        print(f"Closing database connection for request_id: {request_id}")
        db.close()