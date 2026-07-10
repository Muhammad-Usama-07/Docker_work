# 1. Base image (Python ka official image)
FROM python:3.9-slim

# 2. Container ke andar kaam karne ki directory (folder) banayein
WORKDIR /app

# 3. Apni Python file ko container mein copy karein
COPY app.py .

# 4. Jab container chaley toh yeh command run ho
CMD ["python", "app.py"]