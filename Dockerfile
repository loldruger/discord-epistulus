# Stage 1: Build the application
# Use the latest stable Rust on Debian Bullseye slim for the builder
FROM rust:slim-bullseye AS builder

# Install necessary build dependencies for openssl-sys and other native crates
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the Cargo.toml and Cargo.lock files
COPY Cargo.toml Cargo.lock ./

# Create a dummy src/main.rs to allow dependency-only builds
# This helps in caching dependencies if only source code changes later
RUN mkdir src/
RUN echo "fn main() {println!(\"Pre-building dependencies...\");}" > src/main.rs

# Build dependencies only
RUN cargo build --release
# Clean up the dummy executable and its metadata.
RUN rm -f target/release/deps/discord_epistulus*

# Copy the actual application source code
COPY src ./src

# Build the application using the cached dependencies
RUN cargo build --release

# Stage 2: Create the final lightweight image
# Use Debian Bullseye slim for the final image for a smaller footprint
FROM debian:bullseye-slim

# Set the working directory for the final application
WORKDIR /usr/local/bin

# Copy the built binary from the builder stage
COPY --from=builder /usr/src/app/target/release/discord_epistulus .

# Set the command to run when the container starts
CMD ["./discord_epistulus"]