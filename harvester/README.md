# Harvester debugging notes

When Fuseki returns `401 Unauthorized` during sync, work through the checklist below to identify configuration mismatches.

## Quick checks
1. Confirm the harvester knows which dataset to target and which credentials it will use:
   - `docker compose logs harvester | grep -E "Fuseki dataset|Fuseki auth mode"`
   - The harvester prints the dataset name, endpoint, and whether it is using the admin or a service user.
2. Verify environment variables injected into the harvester container match Fuseki's users:
   - `docker compose exec harvester env | grep FUSEKI_`
   - The username/password must exist in `fuseki/shiro.ini` (the admin user is `FUSEKI_ADMIN_USER`/`FUSEKI_ADMIN_PASSWORD`).
3. Check that Fuseki itself accepts the credentials:
   - `curl -u "$FUSEKI_ADMIN_USER:$FUSEKI_ADMIN_PASSWORD" http://localhost:3030/$/ping`
   - `curl -u "$FUSEKI_ADMIN_USER:$FUSEKI_ADMIN_PASSWORD" --data 'update=ASK{}' http://localhost:3030/knowledge-graph/update`
   - Both commands should return `200`; a 401/403 indicates the credentials are wrong or the user lacks rights.

## Dataset creation and permissions
- The harvester attempts to create a TDB2 dataset on startup via the `/$/datasets` admin endpoint. If that call returns 401/403, confirm the admin password in Compose matches the password configured in Fuseki's `shiro.ini`.
- If you customized the dataset name, ensure `FUSEKI_DATASET_NAME` matches the path segment in `FUSEKI_ENDPOINT` (for example, `/my-dataset/update`).

## Inspect Fuseki authentication rules
- Open `fuseki/shiro.ini` inside the Fuseki container to confirm users and roles:
  - `docker compose exec fuseki cat /fuseki/shiro.ini | sed -n '1,120p'`
- By default, updates require the `fuseki` role. Make sure your configured user has that role assigned.

## Log analysis
- Look for authentication errors in Fuseki logs: `docker compose logs fuseki | grep -i auth`
- The harvester will now add a hint when a 401/403 occurs, pointing you back to the Fuseki credentials.

## Resetting credentials in a dev environment
If you suspect old credentials are stuck, remove the persistent Fuseki volume and redeploy so the admin password from Compose is applied afresh:

```bash
docker compose down -v
export FUSEKI_ADMIN_PASSWORD=newpassword
docker compose up -d --build
```

Then re-run the quick checks above.
