FROM rust:alpine
WORKDIR /usr/src/app
COPY . .
RUN cargo build --release

COPY --from=builder /usr/src/app/target/release/discord_epitulus .

CMD ["./discord_epitulus"]
