# --- Stage 1: Base (Common steps for both dev and prod) ---
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .

# --- Stage 2: Development Environment ---
FROM base AS development
EXPOSE 5173
# Start Vite and expose the app outside of the container
CMD ["npm", "run", "dev", "--", "--host"]

# --- Stage 3: Build (Compiles the React app for production) ---
FROM base AS build
RUN npm run build

# --- Stage 4: Production Environment (Nginx web server) ---
FROM nginx:alpine AS production

# Patch OS-level vulnerabilities (like zlib)
RUN apk update && apk upgrade --no-cache

# Copy the built assets from the previous stage to nginx's serving directory
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-https.conf /etc/nginx/templates/nginx-https.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
EXPOSE 443
# Start Nginx
CMD ["/docker-entrypoint.sh"]