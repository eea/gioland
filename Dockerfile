FROM python:2.7-slim

RUN runDeps="gcc make libldap2-dev libsasl2-dev libssl-dev" \
 && apt-get update -y \
 && apt-get install -y --no-install-recommends $runDeps \
 && rm -vrf /var/lib/apt/lists/*

COPY . /gioland
WORKDIR /gioland

RUN pip install -r requirements.txt

ENTRYPOINT ["./docker-entrypoint.sh"]
