# Deploying Civil Buddy on AWS Lightsail

One Lightsail instance per company, used by its estimators and logistics staff in a browser. This guide stands
up that instance with HTTPS, a random access token, and only the SYNTHETIC demo files on it.

> **Status: this procedure has not been run on Lightsail.** No Lightsail instance, static IP or Let's Encrypt
> certificate has been created for it yet. What *was* run is listed under [What was tested](#what-was-tested):
> the same launch script, compose override and Caddy config on a local Docker host (WSL2), and the image's own
> smoke test in CI. When the team runs it on Lightsail, the URL and the results go into this file.

## What gets deployed

```
browser ──HTTPS──> Caddy 2 (ports 80/443, automatic Let's Encrypt certificate)
                     └─ reverse_proxy ──> gateway (FastAPI, 127.0.0.1:8000 only, CIVIL_TOKEN required)
                                            ├─ volume packing_output  /app/output   (SQLite, upload jobs, seeded job folder)
                                            └─ volume agent_out       /app/demo/out (what agent turns write)
```

| File | What it does |
| --- | --- |
| `docker-compose.yml` | The gateway image (`civil-buddy-gateway:0.7.0`), `CIVIL_TOKEN` required, the two volumes. |
| `deploy/lightsail/compose.override.yml` | Replaces `8000:8000` with `127.0.0.1:8000:8000`, adds `caddy:2` on 80/443, sets `CIVIL_JOB_ROOT=/app/output/job`. No model key is passed to any service. |
| `deploy/lightsail/Caddyfile` | `reverse_proxy gateway:8000` for `{$SITE_ADDRESS}`, 16 MB body limit, HSTS, WebSocket and server-sent events pass through, an access log with the token, cookie and `Authorization` header filtered out. |
| `deploy/lightsail/user-data.sh` | The launch script: Docker from Docker's apt repository, the repository at one pinned commit, a random token into a 0600 `.env`, `docker compose up`, the SYNTHETIC files seeded. |
| `deploy/lightsail/test-local.sh` | The local rehearsal of all of the above (not a Lightsail run). |

What a signed-in user can do there: run the tender ↔ packing link on the demo files or on two files they upload
(`/demo`), use the bid-response page (`/`) and the packing workbench (`/workbench`). Every route except `/`,
`/workbench` and `/api/health` needs the token; without it, `/` and `/workbench` show an English page that says what
this is and how to get access.

## Before you start

- An AWS account the team may use, and the AWS CLI v2 configured for it (`aws configure`, or the organisers'
  credentials). Check which region your credits cover; this guide uses **ap-southeast-1 (Singapore)**.
- The commit to deploy: a full 40-character SHA that exists in the repository the script clones
  (default `https://github.com/LUOaini1213/civil-buddy-sme.git`; change `CIVIL_REPO_URL` in the script for another).
- Your own public IP, for SSH: `curl -s https://checkip.amazonaws.com`.

## Step by step (AWS CLI)

All commands run on your laptop. Names: instance `civil-buddy`, static IP `civil-buddy-ip`.

**1. Reserve the static IP first**, so the HTTPS host name is known before the instance boots:

```bash
export AWS_REGION=ap-southeast-1
aws lightsail allocate-static-ip --region ap-southeast-1 --static-ip-name civil-buddy-ip
IP=$(aws lightsail get-static-ip --region ap-southeast-1 --static-ip-name civil-buddy-ip \
       --query 'staticIp.ipAddress' --output text)
SITE="${IP//./-}.sslip.io"          # e.g. 203-0-113-10.sslip.io resolves to 203.0.113.10: a real certificate, no domain
echo "$SITE"
```

With a domain of your own, create an A record pointing at `$IP` and set `SITE=facade.example.com` instead.

**2. Fill in the launch script** (the commit and the host name; nothing secret goes into it):

```bash
SHA=<the 40-character commit to deploy>
sed -e "s/__CIVIL_REF__/$SHA/" -e "s/__SITE_ADDRESS__/$SITE/" deploy/lightsail/user-data.sh > /tmp/user-data.sh
grep -n '^CIVIL_REF=\|^SITE_ADDRESS=' /tmp/user-data.sh
```

**3. Create the instance** (Ubuntu 24.04 LTS, 2 GB RAM / 2 vCPU / 60 GB SSD bundle `small_3_0`):

```bash
aws lightsail create-instances --region ap-southeast-1 \
  --instance-names civil-buddy \
  --availability-zone ap-southeast-1a \
  --blueprint-id ubuntu_24_04 \
  --bundle-id small_3_0 \
  --user-data file:///tmp/user-data.sh \
  --tags key=project,value=civil-buddy
```

Check the two ids against your account first if in doubt:
`aws lightsail get-blueprints --region ap-southeast-1 --query "blueprints[?blueprintId=='ubuntu_24_04'].name"` and
`aws lightsail get-bundles --region ap-southeast-1 --query "bundles[?bundleId=='small_3_0'].[ramSizeInGb,cpuCount,price]"`.

**4. Attach the static IP** once the instance exists (`get-instance-state` says `running`):

```bash
aws lightsail get-instance-state --region ap-southeast-1 --instance-name civil-buddy
aws lightsail attach-static-ip --region ap-southeast-1 --static-ip-name civil-buddy-ip --instance-name civil-buddy
```

**5. Firewall: 80 and 443 from anywhere, 22 from your IP only.** `put-instance-public-ports` replaces every rule
on the instance, so all three go in one call (it also closes the default open 22 from anywhere):

```bash
MYIP=$(curl -s https://checkip.amazonaws.com)
aws lightsail put-instance-public-ports --region ap-southeast-1 --instance-name civil-buddy --port-infos \
  "fromPort=80,toPort=80,protocol=tcp" \
  "fromPort=443,toPort=443,protocol=tcp" \
  "fromPort=22,toPort=22,protocol=tcp,cidrs=${MYIP}/32"
```

Port 8000 is never opened: the gateway listens on 127.0.0.1 only.

**6. Automatic snapshots** (daily; the time is UTC, whole hours only; 18:00 UTC is 02:00 in Singapore):

```bash
aws lightsail enable-add-on --region ap-southeast-1 --resource-name civil-buddy \
  --add-on-request 'addOnType=AutoSnapshot,autoSnapshotAddOnRequest={snapshotTimeOfDay=18:00}'
```

**7. Wait for the first boot** (the image build takes several minutes on 2 vCPU), then check:

```bash
curl -s "https://$SITE/api/health"                                                # public liveness, 200
curl -s -o /dev/null -w '%{http_code}\n' "https://$SITE/api/tools"                # 401 without the token
```

If the certificate is not there yet, Caddy retries on its own; the static IP must be attached for the HTTP-01
challenge to reach it. The setup log is on the instance: `sudo tail -n 50 /var/log/cloud-init-output.log`
(it never contains the token).

**8. Read the token, into your own terminal only:**

```bash
ssh -i <lightsail key>.pem ubuntu@$IP "sudo grep '^CIVIL_TOKEN=' /opt/civil-buddy/.env | cut -d= -f2-"
```

The access link is `https://$SITE/?token=<token>`. Opening it once sets an HttpOnly, SameSite=Strict, Secure
cookie for 30 days and redirects to the same page without the token. Then `https://$SITE/demo` runs the linked
demo in one click.

## Token handover and blast radius

- The link with the token goes **only into the organiser's submission form**. Never into the public repository,
  the video, a slide, a chat channel or an email thread.
- **Rotate it after 10 Oct** (the Finale), and whenever it may have leaked:
  `sudo sed -i "s/^CIVIL_TOKEN=.*/CIVIL_TOKEN=$(openssl rand -hex 32)/" /opt/civil-buddy/.env` and then
  `cd /opt/civil-buddy && sudo docker compose -f docker-compose.yml -f deploy/lightsail/compose.override.yml --env-file .env up -d`.
  Old cookies then get 401 and are cleared.
- What someone with the token can do: everything a user can (write sessions, upload files, delete checkpoints,
  run evaluations). There is one token for all routes and no rate limit in front of it yet. That is why this
  instance holds **synthetic data only and no model or Bedrock key**, so the worst case is a mess that one
  snapshot restore undoes (step 6).
- Bounded by design: uploads are at most 10 MB + 5 MB (Caddy refuses bodies over 16 MB), at most 2 linked runs
  at once, 10 upload jobs kept per session, and nothing calls a model. The linked run never approves anything:
  its record stays `submit_blocked = true`, `confirmed_by_person = false`.
- Logs: uvicorn's access log is off (it printed the `?token=` link); Caddy's access log filters the token query
  parameter, the cookie and the `Authorization` header.

## Updating

```bash
ssh ubuntu@$IP
cd /opt/civil-buddy && sudo git fetch && sudo git checkout --detach <new sha>
sudo docker compose -f docker-compose.yml -f deploy/lightsail/compose.override.yml --env-file .env up -d --build
```

The database, the upload jobs and what agent turns wrote are in the two volumes and survive this; only
`docker compose down -v` deletes them.

## Cost

| Item | Price (ap-southeast-1) |
| --- | --- |
| Instance `small_3_0`: 2 GB RAM, 2 vCPU, 60 GB SSD, 3 TB transfer | US$12 a month |
| Static IP | free while attached to a running instance |
| Automatic snapshots | about US$0.05 per GB-month of snapshot storage |
| Domain | none needed with `sslip.io` |

Prices as listed on the Lightsail pricing page in September 2026; check before relying on them. Stop the instance
and release the static IP when the pilot ends (`aws lightsail delete-instance`, `aws lightsail release-static-ip`).

## What was tested

Nothing below ran on Lightsail. It ran on a local Docker host, WSL2 on the team's Windows laptop, and in CI.

- **The launch script, the compose override and Caddy** — `deploy/lightsail/test-local.sh <commit>`: runs
  `user-data.sh` with Docker already installed (`CIVIL_SKIP_DOCKER_INSTALL=1`) against a local clone at the
  commit, then checks through Caddy. Run on 26 Sep 2026 at commit `3afb036` (Docker Engine 29.1.3 in WSL2, Compose 2.29.7,
  `caddy:2`): **18 of 18 checks passed** on the first run, in 1,826 s, of which 1,177 s were the uncached image
  build and the clone on a busy laptop. The checks: `.env` mode 600 with a 64-hex token; the token not in the
  setup output; the gateway published on `127.0.0.1` only; through Caddy `/api/health` 200, `/api/tools` 401
  without / 401 wrong / 200 with the token; `/` without the token shows the English access page; `?token=` gives
  303 and an HttpOnly cookie; `/demo` with the cookie; the demo route (rev A 6 × 40HQ, rev B 8 × 40HQ, stale S2,
  S3, S6, S7, 5.4 s); a multipart upload 200; a 20 MB body 413; the WebSocket subscribed with the cookie and
  refused without; the job folder seeded with the three SYNTHETIC files only; the typed agent request linked on
  them and its record survived a gateway re-create; the token in no container log (Caddy access log on). Then
  with Caddy's internal CA (`SITE_ADDRESS=localhost`): HTTPS 401/200, a `Secure` cookie, HSTS, HTTP → 308,
  `wss://` subscribed. `shellcheck` 0.11.0 reports nothing on `user-data.sh`, `test-local.sh` and
  `scripts/docker_smoke.sh`. CI runs the same rehearsal in the `docker-smoke` job.
- **The image** — `scripts/docker_smoke.sh` (CI job `docker-smoke` on every PR): the image carries no
  `demo/.env`, `demo/out` or `demo/data`; it refuses to start without `CIVIL_TOKEN`; 401/200 on the token; the
  upload route and the demo route give S1–S7, 6 × 40HQ, and after rev B the stale statements S2, S3, S6, S7; the
  typed agent request writes its link record under `/app/demo/out`, and that record and the database survive a
  container re-create.
- **Static checks** — `scripts/test_deploy_config.py` (in `npm run check`): the override binds the gateway to
  127.0.0.1 with `!override`, the Caddyfile filters the token from its log, the launch script never prints the
  token and seeds only the three SYNTHETIC files.

Not tested anywhere yet: the Docker installation step of `user-data.sh` (the rehearsal skips it), a Let's Encrypt
certificate for an `sslip.io` name, the Lightsail firewall and snapshot commands, and a build on a 2 GB instance.
The launch script is plain bash rather than `#cloud-config`, because a Lightsail launch script is a shell script.
`cloud-init schema` (cloud-init 25.2 on Ubuntu 24.04) recognises it as `text/x-shellscript` and says that type is
not evaluated by the schema check, so it was checked with `bash -n`, `shellcheck` and by running it as above.
