#!/usr/bin/env bash
# Stand up the open-source 5G SA core + UERANSIM using herlesupreeth/docker_open5gs.
# Verified against that repo's commit 1f3bcf7 (2026-09-05): compose file names, container names (nr_gnb, nr_ue),
# image tags, .env keys and the provisioning CLI were read from that revision. NOT executed end-to-end (no Docker in the
# environment this was written in) - expect to adjust if upstream has moved.
set -euo pipefail
REPO_DIR="${REPO_DIR:-$PWD/docker_open5gs}"
PIN="${PIN:-1f3bcf7}"
HOST_IP="${1:-$(hostname -I | awk '{print $1}')}"

need() { command -v "$1" >/dev/null || { echo "missing: $1"; exit 1; }; }
need git; need docker
docker compose version >/dev/null 2>&1 || { echo "docker compose v2 required (>= 2.14)"; exit 1; }

echo "[1/6] host prerequisites"
[ "$(uname -s)" = "Linux" ] || { echo "Linux host required (kernel SCTP for N2); macOS is not supported by this stack"; exit 1; }
sudo modprobe sctp || echo "warn: could not load sctp module"
sudo sysctl -w net.ipv4.ip_forward=1
echo "note: upstream README also disables ufw; this script does not. If the core cannot reach the gNB, check your firewall."

echo "[2/6] clone docker_open5gs @ $PIN"
[ -d "$REPO_DIR/.git" ] || git clone https://github.com/herlesupreeth/docker_open5gs.git "$REPO_DIR"
git -C "$REPO_DIR" fetch -q --all || true
git -C "$REPO_DIR" checkout -q "$PIN" || echo "warn: could not pin to $PIN; using current checkout"

echo "[3/6] pull + tag images (pre-built, per upstream README)"
for img in docker_open5gs docker_grafana docker_metrics docker_ueransim; do
  docker pull "ghcr.io/herlesupreeth/${img}:master"
  docker tag  "ghcr.io/herlesupreeth/${img}:master" "$img"
done

echo "[4/6] set DOCKER_HOST_IP=$HOST_IP in .env"
sed -i "s|^DOCKER_HOST_IP=.*|DOCKER_HOST_IP=${HOST_IP}|" "$REPO_DIR/.env"

echo "[5/6] start 5G SA core"
( cd "$REPO_DIR" && set -a && . ./.env && set +a && docker compose -f sa-deploy.yaml up -d )

echo "[6/6] done. Next:  ./provision_subscriber.sh   then   ./run_experiment.sh"
echo "WebUI (optional): http://${HOST_IP}:9999  (default admin / 1423 - change it)"
