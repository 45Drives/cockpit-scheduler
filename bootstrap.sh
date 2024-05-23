#!/usr/bin/env bash
# bootstrap.sh

set -e
set -o pipefail
set -x

command -v sponge >/dev/null || { echo "Missing 'sponge'. Please install moreutils." >&2 ; exit 1 ; }

jq 'del(.packageManager)' ./package.json | sponge ./package.json

rm .yarnrc.yml .yarn -rf

yarn set version stable

yarn config set nodeLinker node-modules

# hack to fix using legacy cockpit-helpers and cockpit-typings
cat <<'EOF' >> .yarnrc.yml
npmScopes:
  45drives:
    npmRegistryServer: https://npm.pkg.github.com
    npmAlwaysAuth: false
    npmAuthToken: ${NPM_AUTH_TOKEN}
EOF
