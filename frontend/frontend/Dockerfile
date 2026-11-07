# ==========================================
# STAGE 1: Build the Flutter Web App
# ==========================================
# Debian 12 (bookworm): Debian 11 (bullseye) is end-of-life and its security
# mirror no longer serves packages.
FROM debian:bookworm-slim AS build-env

# Install necessary build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils && \
    apt-get clean

# Clone only the latest stable Flutter release and add it to the PATH
RUN git clone --depth 1 -b stable https://github.com/flutter/flutter.git /usr/local/flutter
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

# Download the Dart SDK and web artifacts
RUN flutter config --enable-web && flutter precache --web

# Set the working directory and copy the frontend code
WORKDIR /app
COPY . .

# Fetch dependencies and build the web version
RUN flutter pub get
RUN flutter build web

# ==========================================
# STAGE 2: Serve the App with Nginx
# ==========================================
FROM nginx:alpine

# Copy the compiled web files from the first stage
COPY --from=build-env /app/build/web /usr/share/nginx/html

# Expose port 80 for web traffic
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]