# 1. Slim base image use karein (chhoti size)
FROM python:3.9-slim

# 2. Non-root user create karein (security)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 3. System dependencies install karein (OpenCV ke liye)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. Working directory banayein
WORKDIR /app

# 5. requirements.txt pehle copy karein (caching optimize karne ke liye)
COPY requirements.txt .

# 6. Python dependencies install karein
RUN pip install --no-cache-dir -r requirements.txt

# 7. Baki files copy karein
COPY . .

# 8. Non-root user ko files ka ownership dein
RUN chown -R appuser:appuser /app

# 9. Non-root user par switch karein
USER appuser

# 10. Port expose karein
EXPOSE 5000

# 11. Application run karein
CMD ["python", "app.py"]