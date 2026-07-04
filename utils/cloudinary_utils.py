"""
Cloudinary upload utility.
Reads credentials from environment variables (.env file)
and provides a single upload function used by the upload API endpoint.
"""
import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

def upload_to_cloudinary(file, resource_type='auto', folder='punctuahr'):
    """
    Upload a file to Cloudinary and return the secure URL.
    
    Args:
        file: The file object (from request.FILES)
        resource_type: 'image', 'video', 'raw', or 'auto'
        folder: The Cloudinary folder to organize uploads
    
    Returns:
        dict with 'url' and 'public_id' on success, or raises an exception
    """
    result = cloudinary.uploader.upload(
        file,
        resource_type=resource_type,
        folder=folder,
    )
    return {
        'url': result.get('secure_url'),
        'public_id': result.get('public_id'),
    }
