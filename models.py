# models.py
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure database
os.makedirs(os.path.dirname("data/"), exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Request(Base):
    __tablename__ = 'requests'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default='PENDING')
    progress = Column(Float, default=0.0)
    webhook_url = Column(String(255))
    csv_file_path = Column(String(255), nullable=False)
    output_csv_url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    products = relationship("Product", back_populates="request")

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), ForeignKey('requests.request_id'), nullable=False)
    product_id = Column(String(100), nullable=False)
    image_url = Column(String(255))
    processed_image_url = Column(String(255))
    status = Column(String(20), default='PENDING')
    
    request = relationship("Request", back_populates="products")