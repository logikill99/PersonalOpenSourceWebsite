docker build -t djapp -f ./Dockerfile .
docker run -t -p 8000:8000 --name "PersonalHomePage" djapp