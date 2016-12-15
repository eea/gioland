FROM ubuntu:latest
EXPOSE 5000
RUN apt-get update -y
RUN apt-get install -y python-dev build-essential gcc python-pip git libldap2-dev libsasl2-dev libssl-dev
COPY . /gioland
WORKDIR /gioland
RUN pip install -r requirements.txt
RUN touch .env; echo "WAREHOUSE_PATH=/gioland/instance/warehouse LOCK_FILE_PATH=/gioland/instance/db.lock SECRET_KEY=some random string here">>.env
CMD python manage.py runcherrypy -p 5000 -H 0.0.0.0

