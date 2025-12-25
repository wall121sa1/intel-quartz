FROM postgres:16

COPY services/shared/postgres-entrypoint.sh /opt/quartz/postgres-entrypoint.sh
RUN chmod 755 /opt/quartz/postgres-entrypoint.sh
