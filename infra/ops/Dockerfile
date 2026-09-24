FROM python:3.13-alpine

WORKDIR /app
COPY ops.py ./
COPY static ./static

# /data holds the SQLite history; a new named volume copies this owner.
RUN mkdir /data && chown 65534:65534 /data

ENV PYTHONUNBUFFERED=1
USER 65534:65534
EXPOSE 8080
CMD ["python", "ops.py"]
