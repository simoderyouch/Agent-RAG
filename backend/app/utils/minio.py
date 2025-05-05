from minio import Minio
from minio.error import S3Error
import io
import json

  # Create bucket if it doesn't exist
BUCKET_NAME = "documents"
def initialize_minio():
    """
    Initialize MinIO client and create bucket if it doesn't exist.
    Returns the MinIO client instance.
    """
    try:
        minio_client = Minio(
            "localhost:9000",  # MinIO server address
            access_key="minioadmin",  # Default access key
            secret_key="minioadmin",  # Default secret key
            secure=False  # Set to True if using HTTPS
        )

      

        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
            # Set bucket policy to allow public read access if needed
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"arn:aws:s3:::{BUCKET_NAME}",
                            f"arn:aws:s3:::{BUCKET_NAME}/*"
                        ]
                        
                    }
                ]
            }
            minio_client.set_bucket_policy(BUCKET_NAME, json.dumps(policy))

        return minio_client

    except Exception as e:
        print(f"Error initializing MinIO: {e}")
        raise
