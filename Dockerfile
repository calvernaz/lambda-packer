FROM python:3.10.15-slim

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && \
    pip install .

CMD ["lambda-packer"]
