FROM python:3-alpine
WORKDIR /app
COPY server.py frames.gz ./
CMD ["python", "-u", "server.py", "8080"]
