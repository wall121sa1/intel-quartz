FROM node:22-slim AS builder
RUN npm install -g npm@11.6.4
WORKDIR /usr/src/app
COPY package.json .
COPY package-lock.json* .
COPY scripts/checkNpmVersion.mjs scripts/
RUN npm ci

FROM node:22-slim
RUN npm install -g npm@11.6.4
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUTF8=1
RUN python3 -m venv /opt/quartz-venv \
    && /opt/quartz-venv/bin/pip install --no-cache-dir PyYAML python-frontmatter
WORKDIR /usr/src/app
COPY --from=builder /usr/src/app/ /usr/src/app/
COPY . .
RUN chmod +x start-quartz.sh
ENTRYPOINT ["./start-quartz.sh"]
CMD ["npx", "quartz", "build", "--serve"]
