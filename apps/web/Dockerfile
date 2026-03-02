# Stage 1: Install dependencies
FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY turbo.json ./
COPY packages/ ./packages/
COPY apps/web/ ./apps/web/
RUN pnpm install --frozen-lockfile

# Stage 2: Build
FROM deps AS builder
WORKDIR /app

# Next.js inlines NEXT_PUBLIC_* at build time — must be available here
ARG NEXT_PUBLIC_API_URL=http://localhost:3001
ARG NEXT_PUBLIC_API_TOKEN
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_TOKEN=$NEXT_PUBLIC_API_TOKEN

RUN pnpm turbo build --filter=@gamole/web

# Stage 3: Runtime
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
