#!/bin/bash
# EC2 "User data" script: paste into Advanced details -> User data when launching an
# Amazon Linux 2023 instance. On first boot it builds DailyAnchor from GitHub and serves it
# over HTTPS at https://<public-ip-with-dashes>.sslip.io (Caddy gets the certificate).
# Progress: /var/log/cloud-init-output.log on the instance. Takes ~5 minutes.
set -euxo pipefail

# Change this before launching. MCP clients send it as "Authorization: Bearer <key>".
API_KEY="CHANGE_ME"
# The person's timezone: routine times like 08:00 are in this zone.
TIMEZONE="Europe/Berlin"
REPO="https://github.com/aishsawant0202-tech/dailyanchor.git"

dnf install -y docker git
systemctl enable --now docker

# sslip.io resolves 1-2-3-4.sslip.io to 1.2.3.4, giving a hostname Let's Encrypt can certify.
TOKEN=$(curl -sX PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
HOSTNAME="${PUBLIC_IP//./-}.sslip.io"

git clone "$REPO" /opt/dailyanchor
docker build -t dailyanchor /opt/dailyanchor
docker network create dailyanchor

docker run -d --name dailyanchor --network dailyanchor --restart unless-stopped \
  -v dailyanchor-data:/app/data \
  -e DAILYANCHOR_ALLOWED_HOSTS="$HOSTNAME" \
  -e DAILYANCHOR_API_KEY="$API_KEY" \
  -e TZ="$TIMEZONE" \
  dailyanchor

docker run -d --name caddy --network dailyanchor --restart unless-stopped \
  -p 80:80 -p 443:443 -v caddy-data:/data \
  caddy:2 caddy reverse-proxy --from "$HOSTNAME" --to dailyanchor:8000

echo "Dashboard: https://$HOSTNAME/dashboard  MCP: https://$HOSTNAME/mcp" | tee /opt/dailyanchor-url.txt
