# Use a lightweight Node.js image
FROM node:22-alpine

# Set the working directory
WORKDIR /app

# Copy package files first to cache dependencies
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Vite's default port
EXPOSE 5173

# Start Vite and expose the app outside of the container.
CMD ["npm", "run", "dev", "--", "--host"]