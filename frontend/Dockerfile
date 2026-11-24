FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The standard trial deployment does not include the separate RTMPose service.
ARG VITE_POSE_OFFLINE=browser
ENV VITE_POSE_OFFLINE=${VITE_POSE_OFFLINE}
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
