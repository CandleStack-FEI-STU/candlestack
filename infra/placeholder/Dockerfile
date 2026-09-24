# Placeholder app: shows which environment, version and commit is deployed until the
# real application replaces it. The same image runs in every environment.
FROM caddy:2-alpine

ARG APP_COMMIT=unknown
ENV APP_COMMIT=$APP_COMMIT \
    APP_ENV=local \
    APP_VERSION=dev \
    XDG_CONFIG_HOME=/tmp/config \
    XDG_DATA_HOME=/tmp/data

COPY Caddyfile /etc/caddy/Caddyfile
COPY site /srv

USER 65534:65534
EXPOSE 8080
