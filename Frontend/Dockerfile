FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# Build client (Vite) and server (esbuild)
RUN npm run build

# --- Production stage ---
FROM node:22-alpine

WORKDIR /app

# Need psql client to run the init script
RUN apk add --no-cache postgresql-client

COPY package.json ./
RUN npm install --omit=dev

COPY --from=builder /app/dist ./dist
COPY drizzle.config.ts ./
COPY shared ./shared
COPY tsconfig.json ./
COPY init.sql ./

EXPOSE 3000

# Run idempotent SQL bootstrap then start the production server
CMD ["sh", "-c", "psql $DATABASE_URL -f init.sql && node dist/index.cjs"]
