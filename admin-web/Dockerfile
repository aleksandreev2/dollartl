FROM node:22-alpine AS builder
WORKDIR /app
ARG VITE_API_BASE_URL=""
ARG VITE_ADMIN_DEVELOPMENT_ID=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_ADMIN_DEVELOPMENT_ID=${VITE_ADMIN_DEVELOPMENT_ID}
COPY package.json tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm install && npm run build

FROM nginx:1.29-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
