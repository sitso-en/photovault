import os
import uuid
import magic
import boto3
from django.conf import settings
from botocore.exceptions import ClientError, NoCredentialsError


class StorageException(Exception):
    """Custom exception for storage operations"""
    pass


class S3StorageService:
    """
    AWS S3 Storage Service
    Handles file uploads, validation, and deletion
    """
    
    def __init__(self):
        """Initialize S3 client"""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    def validate_file(self, file):
        """
        Validate uploaded file for:
        - File size
        - MIME type (actual file content, not just extension)
        - File extension
        
        Raises StorageException if validation fails
        """
        # 1. Check file size
        if file.size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
            raise StorageException(
                f"File size exceeds maximum allowed size of {max_size_mb}MB"
            )
        
        # 2. Check actual MIME type using python-magic
        # This reads the file's magic bytes (file signature) to determine real type
        # Prevents attacks like renaming virus.exe to virus.jpg
        file.seek(0)  # Reset file pointer to beginning
        mime = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)  # Reset again for later use
        
        if mime not in settings.ALLOWED_IMAGE_TYPES:
            raise StorageException(
                f"Invalid file type '{mime}'. Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
            )
        
        # 3. Check file extension (additional layer of validation)
        ext = os.path.splitext(file.name)[1][1:].lower()  # Get extension without dot
        if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise StorageException(
                f"Invalid file extension '.{ext}'. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}"
            )
        
        return True
    
    def generate_unique_filename(self, original_filename):
        """
        Generate unique filename using UUID to prevent collisions
        
        Example:
            Input: vacation.jpg
            Output: a3f7b8c9d2e1f4a5b6c7d8e9f0a1b2c3.jpg
        """
        ext = os.path.splitext(original_filename)[1]  # Get extension with dot
        unique_name = f"{uuid.uuid4().hex}{ext}"
        return unique_name
    
    def upload(self, file, filename, folder=None):
        """
        Upload file to S3 bucket
        
        Args:
            file: Django UploadedFile object
            filename: Original filename
            folder: Optional folder path (e.g., 'users/john')
        
        Returns:
            str: Public URL of uploaded file
        
        Raises:
            StorageException: If upload fails
        """
        try:
            # Step 1: Validate file
            self.validate_file(file)
            
            # Step 2: Generate unique filename
            unique_filename = self.generate_unique_filename(filename)
            
            # Step 3: Create full file path with folder
            if folder:
                file_path = f"{folder}/{unique_filename}"
            else:
                file_path = unique_filename
            
            # Step 4: Upload to S3
            file.seek(0)  # Reset file pointer before reading
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                file_path,
                ExtraArgs={
                    'ContentType': file.content_type,  # Set correct MIME type
                    'CacheControl': 'max-age=86400'  # Cache for 1 day
                }
            )
            
            # Step 5: Generate and return public URL
            public_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{file_path}"
            return public_url
            
        except NoCredentialsError:
            raise StorageException(
                "AWS credentials not found. Please check your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NoSuchBucket':
                raise StorageException(
                    f"S3 bucket '{self.bucket_name}' does not exist. Please create it in AWS Console"
                )
            elif error_code == 'AccessDenied':
                raise StorageException(
                    "Access denied. Check your IAM user permissions and bucket policy"
                )
            elif error_code == 'InvalidAccessKeyId':
                raise StorageException(
                    "Invalid AWS Access Key ID. Please check your credentials"
                )
            else:
                raise StorageException(f"S3 upload failed: {str(e)}")
                
        except StorageException:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            raise StorageException(f"Unexpected error during upload: {str(e)}")
    
    def delete(self, file_url):
        """
        Delete file from S3 bucket
        
        Args:
            file_url: Full URL of the file to delete
            Example: https://photovault-storage.s3.amazonaws.com/users/john/photo.jpg
        
        Returns:
            bool: True if successful
        
        Raises:
            StorageException: If deletion fails
        """
        try:
            # Extract file key (path) from URL
            # URL format: https://bucket-name.s3.amazonaws.com/folder/filename.jpg
            # We need: folder/filename.jpg
            file_key = file_url.split(f"{settings.AWS_S3_CUSTOM_DOMAIN}/")[1]
            
            # Delete from S3
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            return True
            
        except ClientError as e:
            raise StorageException(f"S3 delete failed: {str(e)}")
        except IndexError:
            raise StorageException(f"Invalid S3 URL format: {file_url}")
        except Exception as e:
            raise StorageException(f"Unexpected error during delete: {str(e)}")
    
    def file_exists(self, file_url):
        """
        Check if file exists in S3
        
        Args:
            file_url: Full URL of the file
        
        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            file_key = file_url.split(f"{settings.AWS_S3_CUSTOM_DOMAIN}/")[1]
            
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
            
        except ClientError:
            return False
        except Exception:
            return False