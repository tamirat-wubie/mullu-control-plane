FROM rust:1-slim AS builder
WORKDIR /app
COPY . .
RUN cargo build --release -p mind-api -p mind-cli -p mind-worker

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/mind-api /usr/local/bin/mind-api
COPY --from=builder /app/target/release/mind-cli /usr/local/bin/mind-cli
COPY --from=builder /app/target/release/mind-worker /usr/local/bin/mind-worker
ENV RUST_LOG=info
EXPOSE 8080
CMD ["mind-api"]
