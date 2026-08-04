# ==========================================
# STAGE 1: Build the Flutter Web App
# ==========================================
FROM debian:bullseye-slim AS build-env

# Install necessary build tools
RUN apt-get update && \
    apt-get install -y curl git unzip && \
    apt-get clean

# Clone the Flutter repository and add it to the PATH
RUN git clone https://github.com/flutter/flutter.git /usr/local/flutter
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

# Switch to the stable channel and run flutter doctor to initialize
RUN flutter channel stable && flutter upgrade && flutter doctor

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