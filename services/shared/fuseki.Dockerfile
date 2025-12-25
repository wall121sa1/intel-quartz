FROM stain/jena-fuseki:latest

COPY services/shared/fuseki-entrypoint.sh /opt/quartz/fuseki-entrypoint.sh
RUN chmod 755 /opt/quartz/fuseki-entrypoint.sh
