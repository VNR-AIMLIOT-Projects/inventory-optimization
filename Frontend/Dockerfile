FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build client (Vite) and server (esbuild)
RUN npm run build

# --- Production stage ---
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY --from=builder /app/dist ./dist
COPY drizzle.config.ts ./
COPY shared ./shared
COPY tsconfig.json ./

EXPOSE 3000

# Push DB schema then start the production server
CMD ["sh", "-c", "npx drizzle-kit push && node dist/index.cjs"]
