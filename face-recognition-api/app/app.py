import os
import sqlite3
import redis
import cv2
import numpy as np
import base64
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from contextlib import contextmanager
import json
from datetime import datetime

app = FastAPI(title="Face Recognition API", version="1.0")

# ==================== DATABASE (SQLite) ====================

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "face.db")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create tables if they don't exist"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Detection logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                faces_detected INTEGER,
                image_name TEXT,
                file_size INTEGER,
                detection_time REAL
            )
        """)
        
        # Users table (example for future)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("✅ Database initialized successfully!")

# ==================== REDIS ====================

def get_redis():
    """Get Redis connection"""
    try:
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        r.ping()  # Test connection
        return r
    except:
        print("⚠️ Redis not available, running without cache")
        return None

# ==================== FACE DETECTION ====================

# Load face cascade
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

# ==================== API ENDPOINTS ====================

@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    init_db()

@app.get("/")
async def home():
    return {
        "message": "Face Recognition API is running!",
        "docs": "/docs",
        "database": "SQLite",
        "endpoints": {
            "/detect": "POST - Send image for face detection",
            "/health": "GET - Check API health",
            "/logs": "GET - View detection logs"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "service": "face-recognition-api",
        "database": "SQLite"
    }
    
    # Check Redis
    r = get_redis()
    if r:
        health_status["redis"] = "connected"
    else:
        health_status["redis"] = "disconnected"
    
    return health_status

@app.post("/detect")
async def detect_faces(file: UploadFile = File(...)):
    """Detect faces in uploaded image"""
    try:
        import time
        start_time = time.time()
        
        # Read image
        contents = await file.read()
        file_size = len(contents)
        
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
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
        
        detection_time = time.time() - start_time
        
        # ===== SAVE TO SQLITE =====
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO detection_logs 
                (faces_detected, image_name, file_size, detection_time)
                VALUES (?, ?, ?, ?)
                """,
                (len(faces), file.filename, file_size, detection_time)
            )
            conn.commit()
            log_id = cursor.lastrowid
        
        # ===== CACHE IN REDIS =====
        r = get_redis()
        if r:
            cache_key = f"detection:{file.filename}:{log_id}"
            r.setex(
                cache_key,
                3600,  # 1 hour
                json.dumps({
                    "faces_detected": len(faces),
                    "image_name": file.filename,
                    "detection_time": detection_time
                })
            )
        
        return {
            "success": True,
            "log_id": log_id,
            "faces_detected": len(faces),
            "face_locations": [
                {"x": int(x), "y": int(y), "width": int(w), "height": int(h)} 
                for (x, y, w, h) in faces
            ],
            "image_with_boxes": img_base64,
            "detection_time_ms": round(detection_time * 1000, 2),
            "file_size_kb": round(file_size / 1024, 2)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def get_logs(limit: int = 10):
    """Get recent detection logs"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, faces_detected, image_name, 
                   file_size, detection_time
            FROM detection_logs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        
        logs = []
        for row in rows:
            logs.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "faces_detected": row["faces_detected"],
                "image_name": row["image_name"],
                "file_size_kb": round(row["file_size"] / 1024, 2),
                "detection_time_ms": round(row["detection_time"] * 1000, 2)
            })
        
        return {"total": len(logs), "logs": logs}

@app.delete("/logs")
async def clear_logs():
    """Clear all detection logs"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM detection_logs")
        conn.commit()
        deleted_count = cursor.rowcount
    
    return {"success": True, "deleted_records": deleted_count}

@app.get("/stats")
async def get_stats():
    """Get statistics from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Total detections
        cursor.execute("SELECT COUNT(*) FROM detection_logs")
        total_detections = cursor.fetchone()[0]
        
        # Total faces detected
        cursor.execute("SELECT SUM(faces_detected) FROM detection_logs")
        total_faces = cursor.fetchone()[0] or 0
        
        # Average detection time
        cursor.execute("SELECT AVG(detection_time) FROM detection_logs")
        avg_time = cursor.fetchone()[0] or 0
        
        # Last detection
        cursor.execute(
            "SELECT timestamp FROM detection_logs ORDER BY timestamp DESC LIMIT 1"
        )
        last_detection = cursor.fetchone()
        
        return {
            "total_detections": total_detections,
            "total_faces_detected": total_faces,
            "average_detection_time_ms": round(avg_time * 1000, 2),
            "last_detection": last_detection["timestamp"] if last_detection else None
        }