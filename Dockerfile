FROM rust:alpine AS builder
WORKDIR /usr/src/app
COPY . .
RUN cargo build --release

FROM alpine:latest
WORKDIR /usr/src/app

COPY --from=builder /usr/src/app/target/release/discord_epitulus .
CMD ["./discord_epitulus"]
