from flask import Flask, send_from_directory, jsonify, render_template, send_file, request, session, redirect, url_for
import os
from io import BytesIO
import zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from functools import wraps
import uuid
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
import json
import time
import string
import random

# Load environment variables from .env file in development
if os.path.exists('.env'):
    load_dotenv()

# Initialize Flask app with static/template folders
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))  # Get from env or generate

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

# Define folder in Cloudinary for our images
CLOUDINARY_FOLDER = "whiteboard_images"

# Generate a random session ID (6 characters alphanumeric)
def generate_session_id(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))

# Store active sessions with their creation timestamps
ACTIVE_SESSIONS = {}

# Legacy local path (only used if running locally)
IMAGE_DIR = os.environ.get('IMAGE_DIR', 'images')
if not os.path.exists(IMAGE_DIR):
    try:
        os.makedirs(IMAGE_DIR)
    except:
        pass  # In production, we might not have write access, and that's fine

WHITEBOARD_SIZE = (864, 576)  # PDF page size (12x8 inches at 72 DPI)
user_deleted_images = {}  # Track deletions per user session

# Metadata file to store image timestamps
METADATA_FILE = os.environ.get('METADATA_FILE', 'image_metadata.json')

# Load or create metadata file
def load_metadata():
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'r') as f:
                return json.load(f)
        else:
            # Try to initialize metadata from Cloudinary
            try:
                result = cloudinary.api.resources(
                    type="upload",
                    prefix=CLOUDINARY_FOLDER,
                    max_results=500
                )
                
                metadata = {}
                for resource in result.get('resources', []):
                    # Extract filename from public_id
                    public_id = resource['public_id']
                    filename = os.path.basename(public_id)
                    if '.' not in filename:  # Add extension if missing
                        ext = resource['format']
                        filename = f"{filename}.{ext}"
                    
                    # Extract session ID from path (default if not found)
                    path_parts = public_id.split('/')
                    session_id = 'default'
                    if len(path_parts) >= 3:  # format: whiteboard_images/SESSION_ID/filename
                        session_id = path_parts[1]
                    
                    # Use created_at as timestamp if available
                    timestamp = int(time.time())
                    if 'created_at' in resource:
                        try:
                            # Parse ISO timestamp to UNIX timestamp
                            from datetime import datetime
                            dt = datetime.strptime(resource['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                            timestamp = int(dt.timestamp())
                        except:
                            pass
                    
                    # Initialize session in metadata if not exists
                    if session_id not in metadata:
                        metadata[session_id] = {}
                    
                    metadata[session_id][filename] = {
                        "timestamp": timestamp,
                        "cloudinary_id": resource['public_id'],
                        "url": resource['secure_url']
                    }
                
                return metadata
            except Exception as e:
                print(f"Error initializing metadata from Cloudinary: {e}")
                return {}
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return {}

# Save metadata
def save_metadata(metadata):
    try:
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
    except Exception as e:
        print(f"Error saving metadata: {e}")

# Initialize or load image metadata
image_metadata = load_metadata()

# Assign a unique session ID on first request
@app.before_request
def init_user_session():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        user_deleted_images[session['user_id']] = set()

# Serve the main page
@app.route('/')
def index():
    # Clear any existing session
    if 'session_id' in session:
        session.pop('session_id')
    
    return render_template('index.html')

# Create a new session
@app.route('/session/create')
def create_session():
    session_id = generate_session_id()
    # Keep generating until we get a unique ID
    while session_id in ACTIVE_SESSIONS:
        session_id = generate_session_id()
    
    # Store session creation time
    ACTIVE_SESSIONS[session_id] = int(time.time())
    
    # Redirect to the session page
    return redirect(url_for('join_session', session_id=session_id))

# Join an existing session
@app.route('/session/<session_id>')
def join_session(session_id):
    # Check if session exists
    if session_id not in ACTIVE_SESSIONS:
        # Try to look for images with this session - if found, consider it valid
        if session_id in image_metadata and image_metadata[session_id]:
            ACTIVE_SESSIONS[session_id] = int(time.time())
        else:
            return render_template('error.html', message="Session not found or expired")
    
    # Store session ID in user session
    session['session_id'] = session_id
    
    # Render the main page but with session info
    return render_template('index.html', session_id=session_id)

# Test route to check Cloudinary connection
@app.route('/test-cloudinary')
def test_cloudinary():
    try:
        # Get resource types
        resource_types = cloudinary.api.resource_types()
        
        # Also test with a simple ping-like call
        usage_info = cloudinary.api.usage()
        
        return jsonify({
            "message": "Cloudinary connection successful", 
            "resource_types": resource_types,
            "usage_info": usage_info
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-cloudinary-page')
def test_cloudinary_page():
    return render_template('test_cloudinary.html')

# Test upload form
@app.route('/test-upload')
def test_upload_form():
    return render_template('test_upload.html')

# API: Upload image to Cloudinary
@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Get session ID (use 'default' if none)
    session_id = session.get('session_id', 'default')
    
    try:
        # Generate a unique filename based on timestamp
        timestamp = int(time.time())
        extension = os.path.splitext(file.filename)[1].lower()
        filename = f"whiteboard_{timestamp}{extension}"
        
        # Include session ID in the Cloudinary public_id path
        public_id = f"{CLOUDINARY_FOLDER}/{session_id}/{os.path.splitext(filename)[0]}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file,
            public_id=public_id,
            resource_type="image"
        )
        
        # Store metadata with session ID
        if session_id not in image_metadata:
            image_metadata[session_id] = {}
            
        image_metadata[session_id][filename] = {
            "timestamp": timestamp,
            "cloudinary_id": result['public_id'],
            "url": result['secure_url']
        }
        save_metadata(image_metadata)
        
        return jsonify({
            "message": "Upload successful",
            "filename": filename,
            "cloudinary_id": result['public_id'],
            "url": result['secure_url']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API: Delete an image for the current user
@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_image(filename):
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "No session"}), 401  # Unauthorized
    
    # Add to user's deleted images list
    user_deleted_images[user_id].add(filename)
    
    return jsonify({"message": "Deleted"})

# API: List non-deleted images for the current user (sorted by timestamp)
@app.route('/api/images')
def list_images():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "No session"}), 401
    
    # Get the current session ID (use 'default' if none)
    session_id = session.get('session_id', 'default')
    
    # Check if we have metadata for this session
    session_metadata = image_metadata.get(session_id, {})
    
    # Use Cloudinary images for this session
    image_list = []
    for filename, data in session_metadata.items():
        if filename not in user_deleted_images.get(user_id, set()):
            image_list.append({
                "filename": filename,
                "timestamp": data["timestamp"],
                "cloudinary_url": data["url"]
            })
    
    # Sort by timestamp ascending (oldest -> newest)
    sorted_images = sorted(image_list, key=lambda x: x['timestamp'])
    
    return jsonify(sorted_images)

# API: Serve an image (block access to deleted ones)
@app.route('/api/images/<filename>')
def get_image(filename):
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "No session"}), 401
    if filename in user_deleted_images[user_id]: return jsonify({"error": "Not available"}), 404
    
    # Get current session ID
    session_id = session.get('session_id', 'default')
    
    # Try to get from Cloudinary first
    if session_id in image_metadata and filename in image_metadata[session_id]:
        # Redirect to Cloudinary URL
        return redirect(image_metadata[session_id][filename]["url"])
    else:
        # Fallback to local file
        try:
            return send_from_directory(IMAGE_DIR, filename)
        except:
            return jsonify({"error": "Image not found"}), 404

# API: Download all non-deleted images as ZIP
@app.route('/api/download')
def download_all():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "No session"}), 401
    
    # Get current session ID
    session_id = session.get('session_id', 'default')
    
    # Create ZIP with images in the correct order
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        # Get session metadata
        session_metadata = image_metadata.get(session_id, {})
        
        # Use Cloudinary images for this session
        image_list = []
        for filename, data in session_metadata.items():
            if filename not in user_deleted_images.get(user_id, set()):
                image_list.append({
                    "filename": filename,
                    "timestamp": data["timestamp"],
                    "url": data["url"]
                })
        
        # Sort by timestamp ascending (oldest -> newest)
        sorted_images = sorted(image_list, key=lambda x: x['timestamp'])
        
        # Download each image from Cloudinary and add to ZIP
        for img in sorted_images:
            response = requests.get(img['url'])
            if response.status_code == 200:
                zip_file.writestr(img['filename'], response.content)
            
    buffer.seek(0)
    return send_file(buffer, mimetype='application/zip', as_attachment=True, download_name='images.zip')

# API: Generate a PDF with all non-deleted images (one per page)
@app.route('/api/download-pdf')
def download_pdf():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "No session"}), 401
    
    # Get current session ID
    session_id = session.get('session_id', 'default')
    
    # Generate PDF with images in the correct order
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=WHITEBOARD_SIZE)
    
    # Get session metadata
    session_metadata = image_metadata.get(session_id, {})
    
    # Use Cloudinary images for this session
    image_list = []
    for filename, data in session_metadata.items():
        if filename not in user_deleted_images.get(user_id, set()):
            image_list.append({
                "filename": filename,
                "timestamp": data["timestamp"],
                "url": data["url"]
            })
    
    # Sort by timestamp ascending (oldest -> newest)
    sorted_images = sorted(image_list, key=lambda x: x['timestamp'])
    
    # Download each image from Cloudinary and add to PDF
    for img in sorted_images:
        response = requests.get(img['url'])
        if response.status_code == 200:
            img_file = BytesIO(response.content)
            pdf.drawImage(ImageReader(img_file), 0, 0, *WHITEBOARD_SIZE)
            pdf.showPage()  # New page
    
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name='images.pdf')

# Health check endpoint for Render
@app.route('/health')
def health_check():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Use PORT environment variable if available (for Render)
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)