FROM rust:1.81-slim AS builder

WORKDIR /app
COPY Cargo.toml build.rs ./
COPY proto ./proto
COPY src ./src

RUN apt-get update && apt-get install -y --no-install-recommends protobuf-compiler && rm -rf /var/lib/apt/lists/*
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/validator_rust /app/validator_rust

EXPOSE 50051
CMD ["./validator_rust"]
