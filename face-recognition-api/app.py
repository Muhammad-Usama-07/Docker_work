import os
import sys
import base64
import urllib.request
import numpy as np
from flask import Flask, request, jsonify

# ===== FIX: OpenCV import compatibility =====
try:
    import cv2
    # Check if CascadeClassifier exists
    if not hasattr(cv2, 'CascadeClassifier'):
        import cv2.cv2 as cv2
except ImportError:
    import cv2.cv2 as cv2

app = Flask(__name__)

def load_face_cascade():
    """Reliably load face cascade classifier"""
    
    print("🔍 Looking for cascade file...")
    
    # Check local file first (Docker will have it)
    local_path = 'haarcascade_frontalface_default.xml'
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        print(f"✅ Found cascade locally: {local_path}")
        cascade = cv2.CascadeClassifier(local_path)
        if not cascade.empty():
            print("✅ Cascade loaded successfully!")
            return cascade
    
    # Try OpenCV's built-in path
    try:
        if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            builtin = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(builtin):
                cascade = cv2.CascadeClassifier(builtin)
                if not cascade.empty():
                    print(f"✅ Loaded from OpenCV: {builtin}")
                    return cascade
    except:
        pass
    
    # Try older OpenCV path
    try:
        if hasattr(cv2, 'haarcascades'):
            builtin = cv2.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(builtin):
                cascade = cv2.CascadeClassifier(builtin)
                if not cascade.empty():
                    print(f"✅ Loaded from OpenCV: {builtin}")
                    return cascade
    except:
        pass
    
    # Download as last resort
    print("📥 Downloading cascade file...")
    url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
    
    try:
        urllib.request.urlretrieve(url, local_path)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            cascade = cv2.CascadeClassifier(local_path)
            if not cascade.empty():
                print("✅ Downloaded and loaded successfully!")
                return cascade
    except Exception as e:
        print(f"❌ Download failed: {e}")
    
    raise RuntimeError("Could not load face cascade classifier!")

# Print OpenCV info for debugging
print(f"📌 OpenCV version: {cv2.__version__}")
print(f"📌 OpenCV location: {cv2.__file__}")
print(f"📌 Has CascadeClassifier: {hasattr(cv2, 'CascadeClassifier')}")

# Load the cascade
face_cascade = load_face_cascade()

@app.route('/')
def home():
    return jsonify({
        "message": "Face Recognition API is running!",
        "opencv_version": cv2.__version__,
        "endpoints": {
            "/detect": "POST - Send image and get face detection results",
            "/health": "GET - Check API health"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "opencv_version": cv2.__version__,
        "cascade_loaded": not face_cascade.empty()
    })

@app.route('/detect', methods=['POST'])
def detect_faces():
    try:
        # Check if face_cascade is loaded
        if face_cascade is None or face_cascade.empty():
            return jsonify({"error": "Face cascade not loaded"}), 500
        
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
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # Draw rectangles
        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # Convert to base64
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
    print("🚀 Starting Face Detection API...")
    app.run(host='0.0.0.0', port=5000, debug=False)