# Serves the static site with Caddy. Railway builds this automatically on each push.
FROM caddy:2-alpine
WORKDIR /srv
COPY index.html style.css app.js ./
COPY data/ ./data/
CMD ["sh", "-c", "caddy file-server --root /srv --listen :${PORT:-8080}"]
