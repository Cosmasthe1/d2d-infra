#!/usr/bin/env bash
# Add the .env test UE (UE1_*) to the Open5GS subscriber DB via the repo's own CLI.
# UERANSIM's ueransim-ue.yaml uses opType 'OP' with UE1_OP, but Open5GS stores OPc - so we derive OPc from Ki+OP.
# (Entering the OP value in an OPc field is the classic cause of silent authentication failures.)
set -euo pipefail
REPO_DIR="${REPO_DIR:-$PWD/docker_open5gs}"
set -a; . "$REPO_DIR/.env"; set +a
OPC="$(python3 "$(dirname "$0")/derive_opc.py" "$UE1_KI" "$UE1_OP")"
echo "IMSI=$UE1_IMSI  OPc(derived)=$OPC"
docker exec webui misc/db/open5gs-dbctl add_ue_with_apn "$UE1_IMSI" "$UE1_KI" "$OPC" internet
echo "subscriber added (APN internet). Verify in WebUI or: docker exec webui misc/db/open5gs-dbctl showall"
