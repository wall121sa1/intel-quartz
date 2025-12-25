ARG FUSEKI_VERSION=4.10.0
FROM stain/jena-fuseki:${FUSEKI_VERSION}

COPY --chmod=755 services/shared/fuseki-entrypoint.sh /opt/quartz/fuseki-entrypoint.sh

RUN if command -v apt-get >/dev/null 2>&1; then \
      apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
      apk add --no-cache curl; \
    fi

HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD curl -fsS http://localhost:3030/$/ping || exit 1
