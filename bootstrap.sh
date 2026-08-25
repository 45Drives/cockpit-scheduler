#!/usr/bin/env bash
# bootstrap.sh

set -e
set -o pipefail
set -x

command -v sponge >/dev/null || { echo "Missing 'sponge'. Please install moreutils." >&2 ; exit 1 ; }
command -v yarn >/dev/null || { echo "Missing 'yarn'. Please install yarn." >&2 ; exit 1 ; }

jq 'del(.packageManager)' ./package.json | sponge ./package.json

rm .yarnrc.yml .yarn -rf

# Must match houston-common's packageManager pin, otherwise corepack picks a
# different Yarn when the submodule build shells out from inside houston-common/.
yarn set version 4.6.0

yarn config set nodeLinker node-modules
yarn config set enableScripts true
yarn config set approvedGitRepositories --json '["**"]'
