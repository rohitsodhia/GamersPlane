# Pre-staging checklist: v2 staging on a new droplet

In order. Items marked **Needs decision:** have no answer in the repo yet. Nothing here touches v1 staging (`staging.gamersplane.com`), which stays as is.

`<staging-host>` is the new subdomain (such as `beta.gamersplane.com`). `<selector>` is the DKIM selector (`YYYYMMDD`, the day the key is generated). `<droplet-ip>` is the new droplet's public IPv4.

## 0. Decisions and inputs

- [ ] Pick `<staging-host>`. It is also the droplet name (section 1), the mail From domain (`no-reply@<staging-host>`) and `POSTFIX_MYHOSTNAME`.
- [ ] **Needs decision:** API hostname. `docker/nginx/nginx.staging.conf` is an old v1.5 sketch (`apiv15.staging-v15.gamersplane.com`) and is not used by anything; `default.conf.template` takes `API_SERVER_NAMES` from `.env`. Pick e.g. `api.<staging-host>`.
- [ ] **Needs decision:** images hostname (`IMAGES_SERVER_NAMES`, `IMAGES_HOST_NAME`), e.g. `images.<staging-host>`. Avatars are served by the proxy from `./images`.
- [ ] **Needs decision:** TLS approach. The v2 nginx config listens on port 80 only and nothing in `compose.yml` terminates TLS or publishes a port outside dev (see section 6). The cookie is `Secure` whenever `ENVIRONMENT != dev`, so staging will not log in over plain HTTP. What v1 did: its Apache proxy publishes only `127.0.0.1:80`, and its `docker/apache/ssl/` holds a self-signed local CA/cert for dev. There is no certbot/Let's Encrypt setup in the v1 repo, so prod TLS was presumably terminated outside the compose stack (host or DO-level), which is not recorded. Options: host-level nginx/Caddy with Let's Encrypt in front of the proxy container, or a TLS-terminating container added to the compose stack.
- [ ] **Needs decision:** frontend hosting. The `frontend` service is commented out in `compose.yml`, and `docker/Dockerfile-nextjs` is stale (the frontend is TanStack Start/Vite, `npm run build`, not Next.js). Options: build and run it on the droplet (needs a new Dockerfile and compose service), or host it elsewhere. Note `VITE_API_BASE_URL` and `VITE_PAGINATE_PER_PAGE` are baked in at build time.
- [ ] **Needs decision:** staging data source. The prod import (`migration/`) is unbuilt: it only holds BBCode usage queries. Realistic options today are the seed data (section 6) or an empty database.

## 1. Droplet

- [ ] Create the droplet on the existing DigitalOcean account (an older account is the reason outbound SMTP is expected to work).
- [ ] Name it exactly `<staging-host>`. DigitalOcean sets the PTR (reverse DNS) from the droplet name, and mail servers check that the PTR matches the sending hostname.
- [ ] Note `<droplet-ip>`.
- [ ] **Needs decision:** droplet size, region and image (the repo says nothing; Postgres, the API, nginx, postfix and possibly the frontend build all share it).
- [ ] Cloud firewall: inbound 22, 80, 443 only. No inbound 25 is needed (postfix publishes no ports and only sends). Outbound unrestricted.
- [ ] Install Docker Engine and the compose plugin, add your user to the `docker` group.
- [ ] Clone the repo on the droplet and check out the branch to deploy.

## 2. Outbound mail gate (do this before anything else is configured)

- [ ] On the droplet, run:

  ```bash
  docker/email/check_port25
  ```

  The host checks must PASS (the container checks are skipped until postfix is running). If they FAIL, DigitalOcean is blocking SMTP: open a support ticket to lift it, or decide on a relay below.
- [ ] Check `<droplet-ip>` against blocklists (MXToolbox "Blacklist Check", Spamhaus lookup). DigitalOcean ranges are sometimes listed. If listed, destroy and recreate the droplet to get a new IP (and re-do the PTR/DNS below).
- [ ] **Needs decision:** if port 25 is blocked and DO will not lift it, which relay (SES, Brevo, ...)? It needs postfix `relayhost` plus SASL settings in `docker/postfix/main.cf` (not built).

## 3. DKIM key

- [ ] On your own machine (not the droplet), from the repo root:

  ```bash
  docker/email/genkey <staging-host>
  ```

  It writes `docker/opendkim/keys/<staging-host>/<selector>.{private,txt}` and prints the DNS record and the `.env` lines. The keys directory is gitignored.
- [ ] Copy only the private key to the server (never git), same relative path:

  ```bash
  ssh <user>@<droplet-ip> mkdir -p <repo>/docker/opendkim/keys/<staging-host>
  scp docker/opendkim/keys/<staging-host>/<selector>.private <user>@<droplet-ip>:<repo>/docker/opendkim/keys/<staging-host>/
  ```

- [ ] Keep a copy of the key outside the droplet (password manager or backup); regenerating means a new selector and DNS record.

## 4. DNS

Create these at the DNS provider for `gamersplane.com`. SPF is evaluated on the From domain and a subdomain does **not** inherit `gamersplane.com`'s SPF record, so `<staging-host>` needs its own.

- [ ] A: `<staging-host>` -> `<droplet-ip>`
- [ ] A: the API and images hostnames from section 0 -> `<droplet-ip>`. If the frontend ends up hosted elsewhere, `<staging-host>` still has to resolve to the droplet for the PTR check, so that needs a separate sending-hostname decision.
- [ ] TXT on `<staging-host>` itself (SPF): `v=spf1 ip4:<droplet-ip> -all`
- [ ] TXT on `<selector>._domainkey.<staging-host>`: the value printed by `genkey`
- [ ] DMARC: nothing to add. `_dmarc.gamersplane.com` (`p=quarantine`, relaxed alignment) is inherited by subdomains.
- [ ] PTR: set automatically by the droplet name (section 1). Verify, do not set by hand.
- [ ] Verify (run where the private key exists so the DKIM key comparison runs, otherwise it WARNs):

  ```bash
  docker/email/check_dns <staging-host> <selector> <droplet-ip>
  ```

  All lines must PASS. DNS may take a few minutes to propagate.

## 5. `.env` for staging

Copy `.env.example` to `.env` on the droplet and fill it in. `.env.example` is missing several variables the API and compose files read; they are listed under "Not in `.env.example`".

Generate fresh (never reuse dev values):

- [ ] `JWT_SECRET_KEY` (e.g. `openssl rand -hex 32`)
- [ ] `PVAR`: **Needs decision:** its purpose and format are undocumented in the repo; confirm what it is before generating.
- [ ] `DATABASE_PASSWORD` (note `compose.dev.yml` hardcodes `POSTGRES_PASSWORD=test123`; the base `compose.yml` uses `DATABASE_PASSWORD`, which is right for staging)

Set per environment:

- [ ] `ENVIRONMENT`: anything but `dev` (`staging`). Effects: API image built without dev dependencies, auth cookie `Secure`, `EMAIL_ENABLED` defaults to true, no hot-reload.
- [ ] `TZ`, `COOKIE_DOMAIN`, `ROOT_DIR` (`/app`), `PAGINATE_PER_PAGE`, `VITE_PAGINATE_PER_PAGE`
- [ ] `HOST_NAME`: the public frontend URL (https). Used in CORS and in the activation/reset links in emails.
- [ ] `API_HOST_NAME`, `VITE_API_BASE_URL`: the public API URL (https)
- [ ] `API_SERVER_NAMES`: API hostname(s) for nginx `server_name`
- [ ] `DATABASE_DIALECT=postgresql`, `DATABASE_HOST=postgres`, `DATABASE_PORT=5432`, `DATABASE_DATABASE`, `DATABASE_USER`; leave `DATABASE_SSH_USERNAME` unset
- [ ] `CACHE_HOST`, `CACHE_TTL`: the `cache` service is commented out in `compose.yml` and nothing here requires it; **Needs decision:** whether the API still uses it (not verified).
- [ ] Email:
  - `EMAIL_HOST=postfix`, `EMAIL_PORT=25`
  - `OPENDKIM_KEY=./docker/opendkim/keys/<staging-host>/<selector>.private`
  - `OPENDKIM_SELECTOR=<selector>`
  - `POSTFIX_MYHOSTNAME=<staging-host>` (must equal the From domain, or mail is sent unsigned)
  - Leave `EMAIL_ENABLED` unset (defaults to true outside dev)

Not in `.env.example` (add them to the example too):

- [ ] `IMAGES_HOST_NAME`, `IMAGES_SERVER_NAMES` (compose substitutes it into nginx), `IMAGES_DIR` (`/var/www/images`)
- [ ] `V1_HOST_NAME`: used only as an extra CORS origin; leave unset unless v1 needs to call v2
- [ ] `LEGACY_DATABASE_*`: only for the legacy routes; **Needs decision:** whether staging needs the legacy MySQL at all (the legacy code is slated for deletion).

## 6. Bring-up

What the repo does and does not provide today:

- `./compose.sh -e staging up` silently adds nothing: `compose.sh` only adds `compose.<env>.yml` if the file exists, and there is no `compose.staging.yml`. Use `./compose.sh --email up -d` (or `-e prod`, which also adds nothing) for the base stack.
- `compose.yml` publishes only `127.0.0.1:8000` (API). The proxy publishes no ports outside dev (`compose.dev.yml` adds `81:80`), and Postgres publishes none either.
- The base `compose.yml` builds the API with `ENVIRONMENT` defaulting to `prod` in `api/Dockerfile` (the `ENVIRONMENT` build arg is only passed by `compose.dev.yml`), so staging gets the no-dev install.

Checklist:

- [ ] **Needs decision:** write a `compose.staging.yml` (publish proxy ports 80/443 or add TLS termination, frontend service, anything else per the decisions in section 0).
- [ ] Create `./images` (bind-mounted into the API and proxy): `mkdir -p images/avatars`
- [ ] Start the stack:

  ```bash
  ./compose.sh -e staging --email up -d --build
  docker ps
  ```

  Expect `gamersplane-proxy`, `-api`, `-postgres-1`, `-postfix`, `-opendkim`.
- [ ] Run migrations (script is `api/alembic.sh`; it runs `docker compose exec ... alembic` and uses the default compose file, so run it from `api/`):

  ```bash
  cd api && ./alembic.sh upgrade head
  ```

- [ ] Seed data (`cli seed`: referral links, publishers, systems, forums, users, system roles, deck types, a character sheet and a character; the other `cli` commands are `create_user` and `create_game`). **Needs decision:** how to run it. `cli/main.py` connects to `localhost:$DATABASE_PORT`, so it needs the Postgres port reachable from where it runs (not published outside dev) and a `uv` environment for `cli/`. `cli/README.md` is empty. Also check that the seed's demo users and passwords are not left on a staging server people can reach.
- [ ] Create your own admin account (`cli create_user`, same running caveat) or via registration.
- [ ] Check the API: `curl -s http://127.0.0.1:8000/docs` on the droplet, then over the public hostname.

## 7. Email verification

- [ ] Send a test message with a real recipient from the droplet:

  ```bash
  docker/email/send_test <to>
  ```

  Expect an opendkim "DKIM-Signature field added (s=<selector>, d=<staging-host>)" line and `status=sent`.
- [ ] mail-tester.com: copy the one-time address from the site, `docker/email/send_test <that address>`, then open the score page. Aim for 9+/10. A missing SPF record, PTR mismatch or listed IP shows up here.
- [ ] Gmail: send to a Gmail account, open "Show original", and confirm `spf=pass`, `dkim=pass`, `dmarc=pass`, with `header.i=@<staging-host>`.
- [ ] Check it did not land in spam. Mark "not spam" once if it did, then re-test later; a new IP and domain start with no reputation.
- [ ] Register a new user with a Gmail address -> the activation email arrives -> the link (`<HOST_NAME>/activate?token=...`) activates the account. This needs the frontend deployed.
- [ ] Password reset: the email is sent, but its link points to `<HOST_NAME>/reset-password?token=...` and that frontend page does not exist yet (`TODO` in `api/src/app/auth/routes.py`). Verify only that the email arrives with a correct-looking link.
- [ ] Clean up a stuck queue if you tested before DNS was ready: `docker exec gamersplane-postfix postsuper -d ALL`

## 8. Known gaps before inviting testers

- [ ] No `compose.staging.yml`, no frontend service, `docker/Dockerfile-nextjs` is stale (section 0 and 6).
- [ ] No TLS or published proxy ports for non-dev (section 0 and 6).
- [ ] Frontend `/reset-password` page does not exist; password reset cannot be completed.
- [ ] Contact page is unbuilt (nothing in the frontend routes or the API for it), so there is no way for testers to reach you from the site.
- [ ] Postfix `main.cf` has `compatibility_level = 3.8` while Alpine installs Postfix 3.11; postfix logs a compatibility warning at startup. Harmless, but bump the level deliberately after reading the 3.9-3.11 release notes.
- [ ] No postfix queue monitoring or bounce handling: failures are only in `logs/postfix/postfix.log` (root-owned on the host; read via `docker exec gamersplane-postfix cat /var/log/postfix.log`). The API logs and swallows SMTP errors, so a user never sees a failed activation email.
- [ ] `docker/opendkim/opendkim.conf` sets `ReportAddress postmaster@gamersplane.com` and `SendReports yes`; make sure that mailbox exists and is read, since DMARC reports (`rua=mailto:postmaster@gamersplane.com`) go there too.
- [ ] No backups for the `gp_postgres_db` volume or `./images`. **Needs decision:** backup approach, even for staging.
- [ ] Avatar upload hardening (Pillow decompression-bomb limit, error handling, size check) before opening uploads to outside testers.
