import os
import boto3
from botocore.client import Config
import io
from dotenv import load_dotenv

# 1. Load the secret variables from the .env file
load_dotenv()

# 2. Securely grab the credentials
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
ACCESS_KEY = os.environ.get("CF_ACCESS_KEY")
SECRET_KEY = os.environ.get("CF_SECRET_KEY")
BUCKET_NAME = os.environ.get("CF_BUCKET_NAME")
PUBLIC_URL_PREFIX = os.environ.get("CF_PUBLIC_URL_PREFIX")

# 3. Failsafe: Crash the app immediately if a key is missing
if not all([CF_ACCOUNT_ID, ACCESS_KEY, SECRET_KEY, BUCKET_NAME, PUBLIC_URL_PREFIX]):
    raise ValueError("🚨 Missing Cloudflare R2 Credentials in .env file!")

# 4. Initialize the S3 Client pointed at Cloudflare
s3 = boto3.client(
    's3',
    # 🚩 FIX: Removed /{BUCKET_NAME} from the end of the endpoint URL!
    endpoint_url=f"https://{CF_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version='s3v4'),
    # Boto3 sometimes gets picky with R2 regions. 'auto' or 'us-east-1' works best.
    region_name='auto' 
)

def upload_file_to_r2(file_bytes, filename, content_type="image/png"):
    """
    Takes raw file bytes and pushes it to Cloudflare R2.
    """
    try:
        file_obj = io.BytesIO(file_bytes)
        
        print(f"☁️ Uploading {filename} to Cloudflare R2...")
        
        s3.upload_fileobj(
            file_obj,
            BUCKET_NAME,
            filename,
            ExtraArgs={"ContentType": content_type} 
        )
        
        # 🚩 FIX: .rstrip('/') ensures we NEVER get a double slash (//) in our URL
        clean_prefix = PUBLIC_URL_PREFIX.rstrip('/')
        public_url = f"{clean_prefix}/{filename}"
        
        print(f"✅ Upload Success! Public URL: {public_url}")
        return public_url
        
    except Exception as e:
        print(f"❌ Failed to upload to R2: {e}")
        return None