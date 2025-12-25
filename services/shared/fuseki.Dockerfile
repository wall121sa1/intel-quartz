FROM stain/jena-fuseki:latest

COPY --chmod=755 services/shared/fuseki-entrypoint.sh /opt/quartz/fuseki-entrypoint.sh
