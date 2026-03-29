FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-slim AS runner

WORKDIR /app

RUN npm install -g serve

COPY --from=builder /app/dist ./dist

ENV PORT=3000

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
