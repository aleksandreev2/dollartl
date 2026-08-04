FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm install && npm run build

FROM nginx:1.29-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
