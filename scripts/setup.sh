#!/usr/bin/env bash
# ARGUS setup. Idempotent -- safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "==> ARGUS setup"

# --- python env ---------------------------------------------------------------
if [ ! -d .venv ]; then
  echo "--> creating .venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "    python deps ok"

# --- env file -----------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from template -- FILL IT IN before running the brief"
fi

mkdir -p data/ledger docs/decisions .cache

# --- optional tooling for the local MCP servers --------------------------------
command -v uvx >/dev/null 2>&1 \
  && echo "    uvx found (edgar + sqlite MCP available)" \
  || echo "    uvx MISSING -- install uv (https://docs.astral.sh/uv/) for the edgar MCP"

# No npx-based servers are declared: Polymarket, Kalshi, Treasury FiscalData
# and the NY Fed are already covered by argus/sources/ over plain REST, so an
# MCP wrapper for them would be a second way to fetch the same numbers.

# --- connectivity check --------------------------------------------------------
echo "--> checking sources"
python3 scripts/check_sources.py || true

cat <<'EOM'

==> next steps

  1. Fill in .env  (FRED_API_KEY and CONGRESS_API_KEY are free and instant;
     EDGAR_IDENTITY just needs your real email or the SEC blocks you)

  2. Hosted MCPs -- add these yourself in claude.ai Settings > Connectors,
     or: claude mcp add --transport http <name> <url>
       Blockscout      https://mcp.blockscout.com/mcp     (free, no auth)
       Unusual Whales  https://unusualwhales.com/public-api/mcp
       Dune            (see dune.com/blog/dune-mcp)
       Token Terminal  https://mcp.tokenterminal.com

  3. Local MCPs are already declared in .mcp.json -- Claude Code will prompt
     to approve them on first run in this directory.

  4. Log your first prediction so the ledger has something to grade in 90 days:
       python -m argus.ledger add --help

EOM
