ARG FUSEKI_VERSION=latest
FROM stain/jena-fuseki:${FUSEKI_VERSION}

ARG FUSEKI_UID=1000

COPY --chmod=755 services/shared/fuseki-entrypoint.sh /opt/quartz/fuseki-entrypoint.sh

USER root
RUN if command -v apt-get >/dev/null 2>&1; then \
      apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
      apk add --no-cache curl; \
    fi
USER ${FUSEKI_UID}

HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD curl -fsS http://localhost:3030/$/ping || exit 1
