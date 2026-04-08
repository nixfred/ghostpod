FROM caddy:builder AS builder
RUN xcaddy build --with github.com/tailscale/caddy-tailscale

FROM caddy:latest
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile.tailscale /etc/caddy/Caddyfile.tailscale
COPY Caddyfile.lan /etc/caddy/Caddyfile.lan
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
