FROM node:22.11.0-slim AS builder
RUN npm install -g npm@11.6.4
WORKDIR /usr/src/app
COPY services/quartz/package.json .
COPY services/quartz/package-lock.json* .
COPY services/quartz/scripts/checkNpmVersion.mjs scripts/
RUN npm ci

FROM node:22.11.0-slim
WORKDIR /usr/src/app
COPY --from=builder /usr/src/app/ /usr/src/app/
COPY services/quartz/ .
CMD ["bash"]
