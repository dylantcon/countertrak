#!/usr/bin/env bash
# availability watchdog for the containerized countertrak stack.
#
# runs every 30s from countertrak-watchdog.timer. probes web and gsi over
# loopback (the same path nginx uses), independently of docker's internal
# healthchecks. a service that fails two probes 5s apart gets revived:
# `up -d` first (covers a container that isn't running at all), then
# `restart` (covers one that is running but wedged). output lands in the
# journal: journalctl -u countertrak-watchdog.service
set -u

COMPOSE=(docker compose -f /var/www/countertrak.dconn.dev/docker-compose.prod.yml)

WEB_URL="http://127.0.0.1:8000/"
GSI_URL="http://127.0.0.1:3000/status"

probe() {
    curl -fsS --max-time 8 -o /dev/null "$1"
}

check() {
    local svc="$1" url="$2"

    probe "$url" && return 0
    sleep 5
    probe "$url" && return 0

    echo "$svc failed two probes at $url - reviving"
    "${COMPOSE[@]}" up -d "$svc" >/dev/null 2>&1
    sleep 10
    if probe "$url"; then
        echo "$svc revived by 'up -d' (container was not running)"
        return 0
    fi

    "${COMPOSE[@]}" restart "$svc" >/dev/null 2>&1
    sleep 10
    if probe "$url"; then
        echo "$svc revived by restart (container was wedged)"
        return 0
    fi

    echo "$svc STILL DOWN after up+restart - manual attention needed"
    return 1
}

rc=0
check web "$WEB_URL" || rc=1
check gsi "$GSI_URL" || rc=1
exit $rc
