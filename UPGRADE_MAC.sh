#!/bin/zsh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/INSTALL_MAC.sh"
