#!/usr/bin/env bash
set -euo pipefail

# Containers to modify
containers=(
  "upf_sos"
  "upf_ims"
  "upf_internet"
  "upf_default"
)

# Commands to run inside each container
read -r -d '' INNER_CMD <<'EOF' || true
# set public DNS (overwrite)
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf

# ensure non-interactive apt operations
export DEBIAN_FRONTEND=noninteractive

# update and try to install tcpreplay
apt-get update -y || { echo "apt-get update failed"; exit 2; }
apt-get install -y --no-install-recommends tcpreplay || {
  echo "Installation with apt-get failed; attempting apt-get install --fix-missing..."
  apt-get install -y --fix-missing tcpreplay || { echo "tcpreplay install failed in container"; exit 3; }
}

# verify
if command -v tcpreplay >/dev/null 2>&1; then
  echo "tcpreplay installed: $(tcpreplay --version 2>&1 | head -n1)"
else
  echo "tcpreplay not found after install"
  exit 4
fi
EOF

# runner
echo "Starting installation on ${#containers[@]} containers..."
for c in "${containers[@]}"; do
  printf "\n➡ Processing container: %s\n" "$c"

  # check container exists
  if ! docker ps -a --format '{{.Names}}' | grep -xq "$c"; then
    echo "  ⛔ Container '$c' not found. Skipping."
    continue
  fi

  # ensure it's running
  if ! docker ps --format '{{.Names}}' | grep -xq "$c"; then
    echo "  ⚠ Container '$c' exists but is not running. Attempting to start..."
    if ! docker start "$c" >/dev/null; then
      echo "  ⛔ Failed to start container '$c'. Skipping."
      continue
    fi
    echo "  ✅ Started $c"
    # small pause to let networking settle
    sleep 1
  fi

  # run commands as root
  echo "  ▶ Patching /etc/resolv.conf and installing tcpreplay in $c..."
  if docker exec -i --user root "$c" bash -lc "$INNER_CMD"; then
    echo "  ✅ Success: $c"
  else
    echo "  ❌ Failed on container: $c (see output above)"
  fi
done

echo -e "\nDone."
