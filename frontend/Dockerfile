FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
# Install envsubst for PORT variable substitution
RUN apk add --no-cache gettext
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV PORT=5173
EXPOSE 5173
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5173}/ || exit 1
# Substitute PORT env var and start nginx
CMD sh -c 'envsubst "\$PORT" < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g "daemon off;"'
