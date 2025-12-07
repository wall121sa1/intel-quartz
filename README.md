# Intel Quartz

Sharing Obsidian using Quartz, with more stuff

## Fuseki SPARQL explorer

- New dedicated page at `/fuseki-explorer` that builds SPARQL queries against the knowledge-graph dataset.
- Query by entity, place, and date range with presets for mentions, entity/place links, and co-mentions.
- Run the query directly against your Fuseki endpoint and view results alongside an interactive Leaflet map of any geocoded places returned.

## Run the Quartz site in Docker

Use the existing watcher stack, which already includes the Fuseki service the explorer expects. From the `watcher/` directory:

```bash
cd watcher

# Start Quartz alongside the shared Fuseki service (port 8080 for Quartz, 3030 for Fuseki)
docker compose up -d fuseki quartz

# Watch logs
docker compose logs -f quartz
```

Open http://localhost:8080 and navigate to `/fuseki-explorer` to use the SPARQL builder against the shared Fuseki instance.

### Environment overrides

* `FUSEKI_ENDPOINT` – override the SPARQL endpoint URL the explorer calls (defaults to `http://fuseki:3030/knowledge-graph/sparql`).
* `BASE_URI` – set the base namespace used when building URIs (defaults to `http://myvault.com/`).
* `FUSEKI_ADMIN_PASSWORD` – admin password for the Fuseki instance (defaults to `changeme`).

Stop the services with `docker compose down quartz fuseki`. Data persists in the `fuseki-data` volume managed by the watcher stack.
