FROM python:3.12-slim

WORKDIR /app

# Standard LDAP build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libldap2-dev libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh
RUN chmod -R 777 ./*

ENTRYPOINT ["/app/entrypoint.sh"]
