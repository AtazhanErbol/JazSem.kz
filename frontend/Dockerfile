FROM node:22-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
FROM development AS build
RUN npm run build
FROM nginxinc/nginx-unprivileged:1.28-alpine@sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8 AS production
USER root
# Security updates for packages identified by the release image scan.
RUN cp /etc/nginx/nginx.conf /tmp/nginx-unprivileged.conf \
    && apk del nginx-module-geoip nginx-module-image-filter nginx-module-njs nginx-module-xslt \
    && apk add --no-cache nginx=1.28.3-r7 \
    && apk upgrade --no-cache c-ares curl libcrypto3 libcurl libexpat libpng libssl3 libuuid libxml2 libxpm musl musl-utils nghttp2-libs xz-libs zlib \
    && cp /tmp/nginx-unprivileged.conf /etc/nginx/nginx.conf \
    && rm /tmp/nginx-unprivileged.conf
USER 101
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
