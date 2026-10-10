#!/usr/bin/env bash
# Apply a supported firmware preset and verify its read-back. Requires root.
set -euo pipefail
requested_profile=${1:?Usage: set-power-profile.sh performance|balanced}
case "$requested_profile" in performance|balanced) ;; *) exit 2 ;; esac
profile_path=/sys/firmware/acpi/platform_profile
choices=$(< /sys/firmware/acpi/platform_profile_choices)
if [[ " $choices " != *" $requested_profile "* ]]; then
    echo "Firmware does not support $requested_profile" >&2
    exit 1
fi
printf '%s\n' "$requested_profile" > "$profile_path"
[[ $(< "$profile_path") == "$requested_profile" ]]
