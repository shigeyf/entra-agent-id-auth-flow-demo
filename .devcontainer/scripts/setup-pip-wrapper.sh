#!/usr/bin/env bash
# -----------------------------------------------------------
# setup-pip-wrapper.sh
#
# Replace system pip / pip3 with thin wrappers that delegate
# to "uv pip". This prevents accidental use of bare pip in a
# uv-managed project.
# -----------------------------------------------------------
set -euo pipefail

WRAPPER_CONTENT='#!/usr/bin/env bash
# Auto-generated wrapper — redirects pip to uv pip.
# To restore the original pip, re-create the devcontainer.
echo "⚠️  This project uses uv. Redirecting \"pip $*\" → \"uv pip $*\"" >&2
exec uv pip "$@"
'

for bin in pip pip3; do
  target="/usr/local/bin/${bin}"
  if [[ -f "$target" ]]; then
    sudo tee "$target" > /dev/null <<< "$WRAPPER_CONTENT"
    sudo chmod +x "$target"
    echo "✅ Replaced ${target} with uv pip wrapper"
  fi
done
