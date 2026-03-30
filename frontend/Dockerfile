# Stage 1: Build stage
FROM node:22-alpine3.23 AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build the React app
RUN npm run build

# Stage 2: Runtime stage
FROM node:22-alpine3.23

WORKDIR /app

# Install serve to run the production build
RUN npm install -g serve

# Copy built app from builder stage
COPY --from=builder /app/build ./build

# Copy public folder for static assets
COPY --from=builder /app/public ./public

# Expose port
EXPOSE 3000

# Set environment variable
ENV NODE_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

# Start the app
CMD ["serve", "-s", "build", "-l", "3000"]
