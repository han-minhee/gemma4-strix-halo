#!/usr/bin/env bash
set -uo pipefail
hostnamectl
cat /etc/os-release
uname -a
lscpu
free -h
df -h .
id
lspci -nnk | sed -n '/VGA\|Display\|Processing accelerators/,+4p'
ls -l /dev/dri /dev/kfd /dev/accel 2>/dev/null
cat /proc/cmdline
for f in /sys/module/amdgpu/parameters/gttsize /sys/module/ttm/parameters/pages_limit \
    /sys/module/ttm/parameters/page_pool_size /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor \
    /sys/firmware/acpi/platform_profile /sys/class/power_supply/*/online; do
    if [[ -f "$f" ]]; then printf '%s: ' "$f"; cat "$f"; fi
done
for card in /sys/class/drm/card[0-9]/device; do
    for f in mem_info_vram_total mem_info_gtt_total mem_info_vram_used gpu_busy_percent; do
        if [[ -f "$card/$f" ]]; then printf '%s: ' "$card/$f"; cat "$card/$f"; fi
    done
done
command -v vulkaninfo >/dev/null && vulkaninfo --summary
command -v rocminfo >/dev/null && rocminfo | sed -n '/Name:.*gfx/,+15p'
rpm -q mesa-vulkan-drivers vulkan-loader glslc cmake gcc-c++ libquadmath perf sysstat aria2
if [[ -x /srv/amd-halo/rocm-venv/bin/rocminfo ]]; then
    /srv/amd-halo/rocm-venv/bin/rocminfo | sed -n '/Name:.*gfx/,+15p'
    /srv/amd-halo/rocm-venv/bin/python -m pip list --format=freeze | sed -n '/^rocm/p'
fi
command -v docker >/dev/null && docker version && docker compose version && docker ps
ps -eo pid,comm,%cpu,%mem,args --sort=-%cpu | head -25
exit 0
