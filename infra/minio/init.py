import os
import time
import boto3
from botocore.client import Config

s3_endpoint = os.getenv("S3_ENDPOINT", "http://minio:9000")
access_key = os.getenv("S3_ACCESS_KEY", "vigil")
secret_key = os.getenv("S3_SECRET_KEY", "vigilvigil123")

print(f"Connecting to MinIO at {s3_endpoint}...")
s3 = boto3.client(
    "s3",
    endpoint_url=s3_endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

buckets = ["vigil-raw", "vigil-evidence", "vigil-dossiers", "vigil-anchors"]

for attempt in range(30):
    try:
        existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        for bucket in buckets:
            if bucket not in existing:
                s3.create_bucket(Bucket=bucket)
                print(f"Created bucket: {bucket}")
        print("MinIO buckets initialized successfully.")
        break
    except Exception as e:
        print(f"Waiting for MinIO ready... (attempt {attempt+1}/30: {e})")
        time.sleep(2)
