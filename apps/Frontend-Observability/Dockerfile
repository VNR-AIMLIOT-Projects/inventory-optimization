FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# Build client (Vite) and server (esbuild)
RUN npm run build

# --- Production stage ---
FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY --from=builder /app/dist ./dist
COPY drizzle.config.ts ./
COPY shared ./shared
COPY tsconfig.json ./
COPY init.sql ./

RUN mkdir -p /app/storage/uploads && chown -R 1000:1000 /app/storage

EXPOSE 3000

# Run idempotent SQL bootstrap then start the production server
CMD ["node", "dist/index.cjs"]
