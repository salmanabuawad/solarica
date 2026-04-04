#!/usr/bin/env python3
"""Write nginx config with correct upload limit directly via SFTP."""
import paramiko, io

HOST = "185.229.226.37"
USER = "root"
PASS = "KortexDigital1342#"
CONF_PATH = "/etc/nginx/sites-available/solarica.wavelync.com"

CONFIG = r"""server {
    listen 80;
    server_name solarica.wavelync.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name solarica.wavelync.com;

    ssl_certificate     /etc/letsencrypt/live/solarica.wavelync.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/solarica.wavelync.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    root  /opt/solarica/frontend/dist;
    index index.html;

    # Allow very large project/design uploads across all API routes
    client_max_body_size 1G;

    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml image/svg+xml;
    gzip_min_length 1024;

    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;

    # SSE scan-stream: long parse + must not buffer (legacy clients)
    location ~ ^/api/projects/[0-9]+/scan-stream$ {
        proxy_pass         http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Connection        "";
        proxy_read_timeout  900s;
        proxy_send_timeout  900s;
        proxy_buffering     off;
        proxy_cache         off;
        proxy_request_buffering off;
        gzip                off;
        client_max_body_size 1G;
    }

    # POST scan-run: same long-running pipeline, single JSON response (no chunked stream)
    location ~ ^/api/projects/[0-9]+/scan-run$ {
        proxy_pass         http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout  900s;
        proxy_send_timeout  900s;
        proxy_request_buffering off;
        client_max_body_size 1G;
    }

    # Extended timeout for PDF/DXF uploads (scan-strings, pattern detect)
    location ~ ^/api/projects/[0-9]+/(scan-strings|detect-string-pattern) {
        proxy_pass         http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_request_buffering off;
        client_max_body_size 1G;
    }

    location ~ ^/api/projects/[0-9]+/files {
        proxy_pass         http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_request_buffering off;
        client_max_body_size 1G;
    }

    location /api/ {
        proxy_pass         http://127.0.0.1:8010/api/;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_request_buffering off;
        client_max_body_size 1G;
    }

    location /health {
        proxy_pass http://127.0.0.1:8010/health;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8010/docs;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location ~* \.(woff2?|ttf|svg|png|jpg|ico|webp)$ {
        expires 30d;
        add_header Cache-Control "public";
        access_log off;
    }
}
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS)

sftp = ssh.open_sftp()
with sftp.open(CONF_PATH, 'w') as f:
    f.write(CONFIG)
sftp.close()
print("Config written via SFTP")

def run(cmd):
    _, s, e = ssh.exec_command(cmd, timeout=30)
    out = s.read().decode(errors='replace').strip()
    err = e.read().decode(errors='replace').strip()
    if out: print(out)
    if err: print('ERR:', err)

run("nginx -t 2>&1")
run("systemctl reload nginx && echo NGINX_RELOADED")
run("grep client_max /etc/nginx/sites-available/solarica.wavelync.com")
ssh.close()
