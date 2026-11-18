FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./

RUN --mount=type=cache,target=/root/.npm \
    npm ci \
    --no-audit \
    --no-fund \
    --prefer-offline \
    --fetch-retries=5 \
    --fetch-retry-mintimeout=10000 \
    --fetch-retry-maxtimeout=60000 \
    --fetch-timeout=120000 \
    --maxsockets=5

COPY . .

EXPOSE 5173

CMD ["npm","run","dev","--","--host","0.0.0.0"]