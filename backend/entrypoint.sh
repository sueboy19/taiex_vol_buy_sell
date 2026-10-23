#!/bin/sh
set -e

# 既有部署的 volume 可能仍為 root 擁有；修正後降權執行主程序
if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /data || true
    exec gosu appuser:appuser "$@"
fi

exec "$@"
