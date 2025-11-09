from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import boto3
from datetime import datetime
from uuid import uuid4
import os

app = Flask(__name__)

# ----------------- Config -----------------
# ----------------- Config -----------------
db = mysql.connector.connect(
    host="database-1.c036qg226bjf.us-east-1.rds.amazonaws.com",
    user="testing",
    password="testing123",
    database="file_upload_db",
    port=3306
)
cursor = db.cursor()

S3_BUCKET = os.getenv("S3_BUCKET", "s3myfirsttesting")
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("aws_access_key_id"),
    aws_secret_access_key=os.getenv("aws_secret_access_key"),
    region_name=S3_REGION
)

UPLOAD_FOLDER = "uploads/"
LINKS_FOLDER = "links/"

# ----------------- Routes -----------------
@app.route('/')
def index():
    cursor.execute("SELECT id, filename, s3_key, upload_time FROM files ORDER BY upload_time DESC")
    files = cursor.fetchall()
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        original_filename = uploaded_file.filename
        unique_prefix = uuid4().hex

        # 1️⃣ Upload actual file to uploads/
        s3_key = f"{UPLOAD_FOLDER}{unique_prefix}_{original_filename}"
        uploaded_file.stream.seek(0)
        s3.upload_fileobj(
            uploaded_file.stream,
            S3_BUCKET,
            s3_key
        )

        # 2️⃣ Create link object in links/ with website redirect
        link_key = f"{LINKS_FOLDER}{unique_prefix}_{original_filename}"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=link_key,
            WebsiteRedirectLocation=f"/{s3_key}"
        )

        # 3️⃣ Store metadata in DB
