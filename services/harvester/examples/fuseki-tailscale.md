# Deploy Apache Jena Fuseki on AWS Lightsail with Tailscale-only access

This walkthrough sets up Fuseki in Docker on a Lightsail instance that already runs Tailscale. The goal is to keep Fuseki reachable **only** on your tailnet (no public 3030 exposure) while staying beginner-friendly.

## What you'll build
- A Lightsail Linux instance with Docker + Docker Compose.
- Tailscale running on the host, tagged for ACL control (e.g., `tag:fuseki`).
- A Fuseki container using host networking so it listens on the host's `tailscale0` interface.
- Persistent data stored on a host directory (`./fuseki-data`).

## Prerequisites
- An AWS Lightsail Linux instance (Ubuntu/Debian recommended).
- Ability to SSH into the instance (e.g., via Lightsail's browser SSH or your terminal).
- A Tailscale account with admin access to set ACLs and tags.
- Basic command-line familiarity; all commands below assume a new instance.

> Keep the Lightsail firewall and security groups closed to the public for port 3030. Only SSH (22) needs to be open for management.

## 1) Prepare the instance
Update packages and install Docker + the Compose plugin:
```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg lsb-release
# Docker Engine
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# allow current user to run docker (optional; re-login to apply)
sudo usermod -aG docker $USER
```

## 2) Install and log in to Tailscale on the host
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh --advertise-tags=tag:fuseki
```
- Complete the login flow in your browser.
- In the Tailscale admin console, ensure the device shows the `tag:fuseki` tag.
- (Optional) Approve the tag or enable auto-approval for your account.

## 3) Create the Fuseki project
```bash
mkdir -p ~/fuseki && cd ~/fuseki
# Save your admin password in an .env file that Docker Compose will read
echo "ADMIN_PASSWORD=<choose-a-strong-password>" > .env
# Create a data dir writable by UID 1000 (Fuseki container user)
mkdir -p fuseki-data && sudo chown 1000:1000 fuseki-data
# Create docker-compose.yml
cat > docker-compose.yml <<'YML'
version: "3.8"

services:
  fuseki:
    image: stain/jena-fuseki:latest
    container_name: fuseki
    restart: unless-stopped
    # The image writes to /fuseki as UID 1000; keep host dir writable
    user: "1000:1000"
    environment:
      - ADMIN_PASSWORD=${ADMIN_PASSWORD:?set in .env}
    volumes:
      - ./fuseki-data:/fuseki
    # Host networking lets Fuseki listen on the host interfaces (including
    # tailscale0) without publishing a Docker port. Tailnet peers reach
    # tcp/3030 via the host's Tailscale IP or MagicDNS name.
    network_mode: host
    # If host networking is unavailable, replace the above with a
    # localhost-only port binding and front it with `tailscale serve`:
    # ports:
    #   - "127.0.0.1:3030:3030"
YML
```
The compose file uses host networking so Fuseki listens on the host interfaces (including `tailscale0`) without publishing a Docker port.

## 4) Start Fuseki
```bash
docker compose up -d
```
Check logs and confirm it’s listening on port 3030:
```bash
docker compose logs -f
```
If you see `cp: cannot create regular file '/fuseki/shiro.ini': Permission denied`,
ensure `fuseki-data` is owned by UID 1000 (re-run `sudo chown 1000:1000 fuseki-data`).
Data is persisted under `~/fuseki/fuseki-data`.

## 5) Verify tailnet-only access
1. Find the host’s Tailscale IP or MagicDNS name:
   ```bash
   tailscale ip -4
   tailscale status --peers=false
   ```
2. From the **same host**, confirm Fuseki is listening before testing remotely:
   ```bash
   curl http://127.0.0.1:3030/
   sudo ss -tlnp 'sport = :3030'   # should show java/fuseki bound on 0.0.0.0:3030 when using host networking
   ```
3. From a different device on the same tailnet, try:
   ```bash
   curl http://<tailscale-hostname-or-ip>:3030/
   ```
4. Confirm that Fuseki is **not** reachable via the public Lightsail IP on 3030 (it shouldn’t be, because we didn’t publish a public port and the firewall blocks it).

## 6) Set ACLs for who can reach Fuseki
In the Tailscale ACL editor, add a rule so the right users/groups can reach `tag:fuseki` on port 3030:
```json
{
  "grants": [
    { "src": ["group:work"], "dst": ["tag:fuseki"], "ip": ["tcp:3030"] }
  ],
  "tagOwners": {
    "tag:fuseki": ["autogroup:admin", "group:work"]
  }
}
```
Adjust the groups and tag owners to your needs. Save & test the ACLs in the admin console.

### If you can’t reach 100.x.x.x:3030 from another tailnet device
- **Check the container:** `docker compose ps` (should be “Up”), `docker compose logs -f` (look for startup errors).
- **Verify the listener:** `sudo ss -tlnp 'sport = :3030'` should show `java`/`fuseki` bound to `0.0.0.0:3030` (with `network_mode: host`). If it’s only on `127.0.0.1`, ensure host networking is enabled or switch to the localhost + `tailscale serve` option.
- **Confirm Tailscale is up:** `tailscale status --self --peers=false` and that the device is logged in and tagged `tag:fuseki`.
- **ACLs:** Make sure there’s a grant for your user/group to reach `tag:fuseki` on `tcp:3030` and no conflicting denies.
- **Security groups:** Do **not** open 3030 publicly. Only SSH (22) needs to be allowed; Tailscale uses outbound connections.

### Where is the web GUI?
Fuseki’s web interface lives at `http://<tailscale-ip-or-MagicDNS>:3030/` (or `http://127.0.0.1:3030/` from the host). The landing page lets you create/upload datasets and view existing ones; admin actions require the password you set in `.env`.

## 7) Ongoing operations
- **Restart/stop**: `docker compose restart` / `docker compose down`
- **Upgrade Fuseki**: `docker compose pull && docker compose up -d`
- **Back up data**: Snapshot or tar `~/fuseki/fuseki-data`
- **If host networking isn’t allowed**: Change `network_mode: host` to a localhost bind (`127.0.0.1:3030:3030`) and publish it internally with `tailscale serve http 3030` on the host.

You now have Fuseki running on Lightsail, reachable only over your tailnet.
