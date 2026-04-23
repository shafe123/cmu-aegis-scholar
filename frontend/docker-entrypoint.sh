#!/bin/sh
set -eu

CERT_DIR=${NGINX_CERT_DIR:-/etc/nginx/certs}
CERT_FILE=${NGINX_CERT_FILE:-fullchain.pem}
KEY_FILE=${NGINX_KEY_FILE:-privkey.pem}

CERT_PATH="${CERT_DIR}/${CERT_FILE}"
KEY_PATH="${CERT_DIR}/${KEY_FILE}"

if [ -f "${CERT_PATH}" ] && [ -f "${KEY_PATH}" ]; then
  cp /etc/nginx/templates/nginx-https.conf /etc/nginx/conf.d/default.conf
  echo "Starting Nginx with HTTPS using certs from ${CERT_DIR}"
else
  cp /etc/nginx/templates/nginx-http.conf /etc/nginx/conf.d/default.conf
  echo "TLS files not found at ${CERT_PATH} and ${KEY_PATH}; starting Nginx on HTTP port 80"
fi

exec nginx -g 'daemon off;'
