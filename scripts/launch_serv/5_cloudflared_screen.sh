#!/bin/bash


base=$(git rev-parse --show-toplevel)
source $base/../launch_env

screen -S cloudflare bash -c \
	"nix develop --command bash -c 'cloudflared tunnel --no-autoupdate run --token $CF_TUN_TOKEN'"


