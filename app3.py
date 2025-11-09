from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import boto3
from datetime import datetime
from uuid import uuid4
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ----------------- MySQL Config -----------------
db = mysql.connector.connect(
    host="database-1.c036qg226bjf.us-east-1.rds.amazonaws.com",
    user="testing",
    password="testing123",
    database="file_upload_db",
    port=3306
)
cursor = db.cursor()

# ----------------- S3 Config -----------------
S3_BUCKET = os.getenv("S3_BUCKET", "s3myfirsttesting")
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
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

        # 1️⃣ Upload file to S3 with attachment disposition
        s3_key = f"{UPLOAD_FOLDER}{unique_prefix}_{original_filename}"
        uploaded_file.stream.seek(0)
        s3.upload_fileobj(
            uploaded_file.stream,
            S3_BUCKET,
            s3_key,
            ExtraArgs={'ContentDisposition': f'attachment; filename="{original_filename}"'}
        )

        # 2️⃣ Optional: create a link object for website redirect
        link_key = f"{LINKS_FOLDER}{unique_prefix}_{original_filename}"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=link_key,
            WebsiteRedirectLocation=f"/{s3_key}"
        )

        # 3️⃣ Store metadata in DB
        upload_time = datetime.utcnow()
        cursor.execute(
            "INSERT INTO files (filename, s3_key, upload_time) VALUES (%s, %s, %s)",
            (original_filename, s3_key, upload_time)
        )
        db.commit()
        return redirect(url_for('index'))

    return "No file selected", 400

@app.route('/download/<int:file_id>')
def download_file(file_id):
    # Fetch filename and S3 key from DB
    cursor.execute("SELECT filename, s3_key FROM files WHERE id=%s", (file_id,))
    file_record = cursor.fetchone()
    if not file_record:
        return "File not found", 404
    
    filename, s3_key = file_record

    # Generate presigned URL with forced download
    presigned_url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': S3_BUCKET,
            'Key': s3_key,
            'ResponseContentDisposition': f'attachment; filename="{filename}"'
        },
        ExpiresIn=3600  # link valid for 1 hour
    )
    return redirect(presigned_url)

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    # Fetch file S3 key from DB
    cursor.execute("SELECT s3_key FROM files WHERE id=%s", (file_id,))
    file_record = cursor.fetchone()
    if file_record:
        s3_key = file_record[0]

        # Delete file from S3
        s3.delete_object(Bucket=S3_BUCKET, Key=s3_key)

        # Delete DB record
        cursor.execute("DELETE FROM files WHERE id=%s", (file_id,))
        db.commit()

    return redirect(url_for('index'))

# ----------------- Run Flask App -----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
