FROM node:22-slim AS builder
RUN npm install -g npm@11.6.4
WORKDIR /usr/src/app
COPY package.json .
COPY package-lock.json* .
COPY scripts/checkNpmVersion.mjs scripts/
RUN npm ci

FROM node:22-slim
RUN npm install -g npm@11.6.4
WORKDIR /usr/src/app
COPY --from=builder /usr/src/app/ /usr/src/app/
COPY . .
CMD ["npx", "quartz", "build", "--serve"]
