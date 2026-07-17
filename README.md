# Docker_work


Build aur Run Flask App:

docker build -t my-flask-app:v1 .
docker run -d --name flask-container -p 8080:5000 my-flask-app:v1

Open the browser the see the app
http://localhost:8080

