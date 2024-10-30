docker build -t "python" --no-cache -f "./Dockerfile" .
docker run -it --rm --name "djapp" python:3.13.0-alpine "python"