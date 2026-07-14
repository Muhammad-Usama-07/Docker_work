import cv2
import numpy as np
from flask import Flask, request, jsonify
from PIL import Image
import io
import base64
import os

app = Flask(__name__)

# Simple face detection using OpenCV's pre-trained classifier
import cv2
import os
import urllib.request

def load_face_cascade():
    """Reliably load face cascade classifier"""
    
    # Try multiple paths
    possible_paths = [
        # 1. OpenCV's built-in path
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml',
        
        # 2. Current directory
        'haarcascade_frontalface_default.xml',
        
        # 3. User's home directory
        os.path.expanduser('~') + '/haarcascade_frontalface_default.xml',
        
        # 4. Download if none exist
        None  # Will trigger download
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"✅ Found cascade at: {path}")
            cascade = cv2.CascadeClassifier(path)
            if not cascade.empty():
                return cascade
    
    # If we get here, download the file
    print("📥 Downloading cascade file...")
    url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
    local_path = "haarcascade_frontalface_default.xml"
    
    try:
        urllib.request.urlretrieve(url, local_path)
        print(f"✅ Downloaded to: {local_path}")
        cascade = cv2.CascadeClassifier(local_path)
        if not cascade.empty():
            return cascade
    except Exception as e:
        print(f"❌ Download failed: {e}")
    
    raise RuntimeError("Could not load face cascade classifier!")

# Use this instead of the old line
face_cascade = load_face_cascade()

@app.route('/')
def home():
    return jsonify({
        "message": "Face Recognition API is running!",
        "endpoints": {
            "/detect": "POST - Send image and get face detection results",
            "/health": "GET - Check API health"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/detect', methods=['POST'])
def detect_faces():
    try:
        # Check if image is in request
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        # Get image from request
        file = request.files['image']
        
        # Read image
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Invalid image"}), 400
        
        # Convert to grayscale (face detection works better)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # Draw rectangles around faces
        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # Convert back to base64 for response
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            "faces_detected": len(faces),
            "face_locations": [{"x": int(x), "y": int(y), "width": int(w), "height": int(h)} for (x, y, w, h) in faces],
            "image_with_boxes": img_base64
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)