FROM python:2.7-slim

RUN apt-get update -y
RUN apt-get install -y python-dev build-essential gcc python-pip git libldap2-dev libsasl2-dev libssl-dev

COPY . /gioland
WORKDIR /gioland
RUN pip install -r requirements.txt
RUN mkdir -p /gioland/instance/

ENTRYPOINT ["./docker-entrypoint.sh"]
