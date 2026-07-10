# 1. Base image (Python ka official image)
FROM python:3.9-slim

# 2. Container ke andar kaam karne ki directory (folder) banayein
WORKDIR /app

# Flask install karein
RUN pip install flask

# 3. Apni Python file ko container mein copy karein
COPY flask_app.py .

# 4. Jab container chaley toh yeh command run ho
CMD ["python", "flask_app.py"]