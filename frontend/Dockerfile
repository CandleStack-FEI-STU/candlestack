# Frontend placeholder: a static page that shows which environment, version and commit is
# deployed, until the real frontend replaces it. The same image runs in every environment;
# the edge Caddy routes /api/* to the backend and everything else here.
FROM caddy:2-alpine

ARG APP_COMMIT=unknown
ENV APP_COMMIT=$APP_COMMIT \
    APP_ENV=local \
    APP_VERSION=dev \
    XDG_CONFIG_HOME=/tmp/config \
    XDG_DATA_HOME=/tmp/data

COPY Caddyfile /etc/caddy/Caddyfile
COPY site /srv

# The upstream binary carries cap_net_bind_service, which cannot be executed once the
# container drops all capabilities. Port 8080 needs none, so copy it without the file caps.
RUN cp /usr/bin/caddy /usr/bin/caddy.nocap && mv /usr/bin/caddy.nocap /usr/bin/caddy

USER 65534:65534
EXPOSE 8080
