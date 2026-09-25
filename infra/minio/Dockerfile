FROM golang:1.24-bookworm AS build
RUN git clone --depth 1 --branch RELEASE.2025-04-22T22-12-26Z https://github.com/minio/minio.git /src
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/minio .
FROM debian:bookworm-slim
RUN useradd --uid 10001 --create-home minio && mkdir /data && chown minio:minio /data
COPY --from=build /out/minio /usr/local/bin/minio
USER minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
