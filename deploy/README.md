# deploy

Publishes real files to a real, internet-facing authoritative BIND nameserver via RFC
2136 dynamic DNS updates, and provides the one-time VPS/zone bootstrap this depends on.
Two real bugs found while first standing this up against actual infrastructure are
already reflected in the templates/code below.

## Prerequisites

- A VPS running Ubuntu with `bind9` installed (`sudo apt install -y bind9 bind9-utils`),
  reachable on a public IP, with SSH key-only access as a non-root user.
- A domain delegated to that VPS (glue record for `ns1.<your-domain>` pointing at the
  VPS's public IP — see "Domain delegation" below).
- A TSIG key generated on the VPS (see "TSIG key" below).
- Local env vars set (see "Configuration" below) before running `deploy.cli`.

## VPS setup (one-time, manual)

1. **Install BIND**: `sudo apt install -y bind9 bind9-utils`.
2. **Two firewall layers, both required** if on a cloud provider — confirmed the hard
   way on Oracle Cloud:
   - The provider's own cloud-level firewall (e.g. Oracle's VCN "Security List") needs
     explicit ingress rules for `53/tcp` and `53/udp` from `0.0.0.0/0`, stateful.
   - The guest OS's own packet filter. On Oracle's stock Ubuntu image this is a
     pre-configured `iptables` ruleset (not `ufw`, which isn't even installed) with a
     default-deny `REJECT` on the `INPUT` chain — only `RELATED,ESTABLISHED`, loopback,
     ICMP, and `tcp dpt:22` are allowed by default. You must insert `ACCEPT` rules for
     `tcp dpt:53`/`udp dpt:53` *above* that REJECT rule, then persist them:
     ```
     sudo iptables -I INPUT <n> -p tcp --dport 53 -j ACCEPT
     sudo iptables -I INPUT <n+1> -p udp --dport 53 -j ACCEPT
     sudo iptables -L INPUT -n -v --line-numbers   # confirm order: ACCEPT rules above REJECT
     sudo apt install -y iptables-persistent        # prompts to save current rules -- say yes
     ```
     Without persisting, the rules are memory-only and silently vanish on reboot.
3. **Generate the TSIG key**:
   ```
   sudo tsig-keygen -a hmac-sha256 update-key | sudo tee /etc/bind/update.key
   sudo chown root:bind /etc/bind/update.key
   sudo chmod 640 /etc/bind/update.key
   ```
   The `secret` value is the single most sensitive credential in this whole setup —
   anyone holding it can write arbitrary records into the zone. View it once
   (`sudo cat /etc/bind/update.key`) and copy it directly into your local env file (see
   "Configuration" below) — never paste it into a chat/ticket/log, and regenerate
   immediately if it ever is.
4. **Write `/etc/bind/named.conf.options`** from `named.conf.options.template` in this
   directory — no placeholders in it, since `listen-on { any; }` is correct as-is (see
   note below on why, not the VPS's specific public IP).
5. **Write `/etc/bind/named.conf.local`** from `named.conf.local.template`, substituting
   your real domain for `<YOUR_DOMAIN>`.
6. **Create the zone file's directory** — note this is `/var/lib/bind/`, **not**
   `/etc/bind/zones/`:
   ```
   sudo mkdir -p /var/lib/bind
   sudo chown bind:bind /var/lib/bind
   ```
7. `sudo named-checkconf && sudo systemctl restart bind9 && sudo systemctl status bind9`
   — confirm `active (running)` with no errors before proceeding. `deploy.cli bootstrap`
   (see below) writes the actual initial zone file into place.
8. **Create a dedicated, unprivileged `deploy` user** — this is who `deploy.cli
   bootstrap` actually SSHes in as (`DeployConfig`'s default `ssh_user` is `"deploy"`);
   don't run it as your main admin account. Least-privilege reasoning: the automated
   tooling only ever needs to write into `/var/lib/bind/` and restart BIND, not full
   root.
   ```
   sudo adduser --disabled-password --gecos "" deploy
   sudo mkdir -p /home/deploy/.ssh
   sudo cp /home/ubuntu/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
   sudo chown -R deploy:deploy /home/deploy/.ssh
   sudo chmod 700 /home/deploy/.ssh
   sudo chmod 600 /home/deploy/.ssh/authorized_keys

   sudo usermod -aG bind deploy
   sudo chmod g+w /var/lib/bind

   echo 'deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart bind9, /usr/sbin/rndc status' | sudo tee /etc/sudoers.d/deploy-rndc
   sudo chmod 440 /etc/sudoers.d/deploy-rndc
   sudo visudo -c
   ```
   The sudo rule only grants `systemctl restart bind9` (what `restart_remote_bind`
   actually calls — see the "Real finding" note below on why it's a restart, not
   `rndc reload`) plus `rndc status` (a harmless read-only diagnostic, not called by
   any code here but useful to allow for manual troubleshooting). Validate from your own
   machine before trusting it: `ssh deploy@<vps_ip> whoami`, `ssh deploy@<vps_ip> sudo
   systemctl restart bind9`, and a test write into `/var/lib/bind/`.

   **On the SSH key itself**: since `push_zone_file`/`restart_remote_bind` call plain
   `ssh`/`rsync` with no `-i` flag, they rely on SSH's own default key lookup — which
   won't find a non-default-named key file automatically. Add a `Host` entry to
   `~/.ssh/config` on whichever machine runs `deploy.cli` mapping the VPS's IP to the
   right `IdentityFile`, rather than hardcoding a key path into this package's code:
   ```
   Host <VPS_PUBLIC_IP>
       IdentityFile ~/.ssh/<your-key-file>
       IdentitiesOnly yes
   ```

### Why `listen-on { any; }`, not the VPS's public IP

A cloud VM's "public IP" is NAT-mapped at the provider's networking layer — the guest OS
itself only ever sees its private IP on its own network interface (confirm with
`ip addr` or the login banner). Configuring `listen-on` with the public IP directly
means BIND tries to bind to an address that doesn't exist locally, which can fail
silently. `any` binds to whatever local interfaces actually exist and lets the
provider's NAT handle public-IP translation, which it already does regardless. This is
unrelated to the zone *content*'s NS/A records, which correctly use the real public IP
(via `build_zone`'s `ns_ip` parameter).

### Why the zone file lives in `/var/lib/bind/`, not `/etc/bind/zones/`

Ubuntu's `bind9` package ships an AppArmor confinement profile for `named` that permits
read access under `/etc/bind/` but not write — confirmed via `dmesg | grep -i apparmor`
showing `DENIED ... operation="mknod" ... name=".../*.zone.jnl" ... profile="named"`.
Every dynamic update needs to create/append a `.jnl` journal file next to the zone file
for durability; AppArmor silently blocks this even when standard Unix permissions
(`chown bind:bind`) are already correct, since it's a separate confinement layer.
`/var/lib/bind/` is one of the paths Ubuntu's default profile already permits read-write,
sidestepping the issue rather than requiring a custom AppArmor profile edit.

## Domain delegation

1. Register your domain at any registrar.
2. Create a glue record: `ns1.<your-domain>` -> `<VPS_PUBLIC_IP>`. This is required
   (not optional) because `ns1.<your-domain>` is inside the domain it delegates for —
   resolving its IP would otherwise require querying the domain's own nameservers,
   i.e. itself. Some registrars additionally require a second NS hostname even for one
   physical server; if so, a second glue record for the same IP satisfies that
   requirement (not real redundancy) — but check first, since not all registrars
   actually require this (Porkbun, for one, didn't).
3. Point the domain's nameservers at `ns1.<your-domain>` in the registrar's UI.
4. Confirm propagation: `dig NS <your-domain>` (no `@` override) shows your nameserver.

## Configuration

All config is env vars, loaded by `deploy.config.DeployConfig.from_env()` — no config
file, no committed secrets:

```
export DNSSTORE_ORIGIN="<your-domain>."          # trailing dot
export DNSSTORE_VPS_IP="<VPS_PUBLIC_IP>"
export DNSSTORE_TSIG_SECRET="<the secret from /etc/bind/update.key>"

# Optional, sensible defaults shown:
# export DNSSTORE_TSIG_KEY_NAME="update-key"
# export DNSSTORE_SSH_HOST="$DNSSTORE_VPS_IP"
# export DNSSTORE_SSH_USER="deploy"
# export DNSSTORE_SSH_PORT="22"
# export DNSSTORE_REMOTE_ZONE_PATH="/var/lib/bind/<your-domain>.zone"
# export DNSSTORE_LOCAL_ZONE_PATH="/tmp/<your-domain>.zone"
```

Save this in a file outside the repo (e.g. `~/.config/dnsfileshare/deploy.env`),
`chmod 600` it, and `source` it before running any `deploy.cli` command — the same
discipline as an SSH private key, just without SSH's built-in file-location convention.

## Usage

```
source ~/.config/dnsfileshare/deploy.env

python -m deploy.cli bootstrap                          # one-time: writes + loads the initial header-only zone
python -m deploy.cli publish ./somefile.pdf --name a.pdf # publishes a file, prints pointer_hash + key
python -m deploy.cli verify <pointer_hash> <key>         # confirms a fresh publish resolves correctly
```

`bootstrap` is the only command that uses SSH — it's a one-time step that gets the zone
into a minimally valid state (SOA/NS/A, no chunk records yet) before any dynamic update
can be sent, since RFC 2136 UPDATE can only modify a zone BIND already has loaded, not
create one from nothing. Every `publish` afterward is a direct, TSIG-signed DNS UPDATE
message over the network — no SSH involved in the steady-state path.

**Real finding, confirmed live**: `bootstrap` restarts BIND via `sudo systemctl restart
bind9`, not `rndc reload`. Once a zone has `allow-update` configured (ours does, from
the start), BIND flatly refuses `rndc reload` on it (`rndc: 'reload' failed: dynamic
zone`) to protect the journal's consistency — confirmed by testing it directly against
the live server. A full restart re-reads the on-disk zone file regardless of dynamic
status, and is fine here specifically because `bootstrap` only ever runs once, before
the zone has received real traffic — a brief full outage is a non-issue for a one-time
setup step, unlike for a routine reload. (Confirmed separately: a restart correctly
syncs the dynamic-update journal into the on-disk zone file first — a real record
published via `nsupdate`/`deploy.cli publish` before the restart was still resolvable
immediately after.)

`publish` prints the `pointer_hash` and base64 `key` to stdout with a "save this now"
warning — there's no durable credentials store yet (planned for a later scaling phase),
so this is the operator's only chance to record them.

## Verification checklist (V1-V11)

Run all of these from your own machine, never via an SSH session on the VPS — the point
is confirming things work from a genuinely external vantage point.

1. **V1.** SSH access as the unprivileged deploy user works.
2. **V2.** `dig NS <your-domain>` shows your nameserver — delegation propagated.
3. **V3.** `dig @<vps_ip> <your-domain> SOA` — VPS answers authoritatively.
4. **V4.** `python -m deploy.cli bootstrap` — header-only zone loads cleanly.
5. **V5.** `python -m deploy.cli publish <path>` — prints `pointer_hash` + `key`, no
   `DeployError`.
6. **V6.** `dig @<vps_ip> <hash>.chunks.<your-domain> TXT +short` for a known chunk
   hash — payload matches.
7. **V7.** UDP-truncation/TCP-fallback still works over the real network path:
   `dig ... +notcp +ignore` (check `tc` flag) then `+tcp` (confirm full answer).
8. **V8.** `python -m deploy.cli verify <pointer_hash> <key>` — recovers the exact
   original file name and bytes.
9. **V9 (stretch).** Repeat V8 with `--resolver-ip 8.8.8.8` instead of the VPS directly
   — first sanity check of public-resolver-mediated resolution.
10. **V10.** `dig @<vps_ip> google.com A` should come back refused/no-answer, not
    recursively resolved — confirms `recursion no` is actually effective, not just
    configured.
11. **V11.** Publish a second file, then re-run V6/V8 against the **first** file's
    `pointer_hash` — confirms dynamic-update accumulation actually works (this is the
    direct test of the correctness gap that motivated using RFC 2136 over full
    zone-file regeneration in the first place).
