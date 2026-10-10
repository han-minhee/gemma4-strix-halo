# Setup

The measured host used Fedora 44 on AC power. The commands below reproduce the baseline; they do not provision storage or change boot/firmware settings. Default examples use `/srv/amd-halo`; adapt paths and device permissions to your machine.

## Build & models

```sh
sudo dnf --refresh install git cmake gcc-c++ ninja-build vulkan-loader-devel \
  mesa-vulkan-drivers vulkan-tools glslc spirv-headers-devel openssl-devel \
  python3-pip moby-engine docker-cli docker-compose container-selinux
bash scripts/build.sh vulkan
python3 scripts/download.py Q4_K_M MTP --directory /srv/amd-halo/models
```

[`versions.json`](../versions.json) pins the runtime commit, model revision, sizes, and SHA256 checksums. The Q4_K_M target is 18.32 GB; the Q8 assistant is 0.51 GB. Allow additional storage for builds and caches.

Native HIP is optional:

```sh
python3 -m venv /srv/amd-halo/rocm-venv
/srv/amd-halo/rocm-venv/bin/pip install \
  --index-url https://stable.repo.amd.com/rocm/whl-next/ \
  'rocm[libraries,devel,device-gfx1151]==10.1.0'
export PATH=/srv/amd-halo/rocm-venv/bin:$PATH
rocm-sdk init
rocm-sdk test
export HIP_PATH=$(rocm-sdk path --root)
bash scripts/build.sh hip
```

## Serve the baseline

```sh
sudo docker build --build-arg BACKEND=vulkan -t amd-halo-gemma4:vulkan .
sudo docker image inspect amd-halo-gemma4:vulkan --format '{{.Id}}'
cp .env.example .env
```

Set `HALO_IMAGE` to the inspected image ID, `RENDER_GID` to the render-device group, and `API_KEY_FILE` to a private file outside Git. Create `/srv/amd-halo/cache` writable by UID 1000. The Compose container uses UID/GID 1000; adapt those IDs if needed.

```sh
sudo docker compose -f compose.yaml -f compose.mtp.yaml up -d
python3 scripts/validate_service.py --url http://127.0.0.1:8080 \
  --key-file /srv/amd-halo/secrets/api-key --output results/service-validation.json
```

The authenticated OpenAI-compatible endpoint is `http://127.0.0.1:8080/v1`, with model alias `gemma-4-31b`. It binds to loopback; use an SSH tunnel for remote access. API reasoning remains enabled by default.

## Profile

```sh
python3 scripts/http_profile.py --url http://127.0.0.1:8080 \
  --key-file /srv/amd-halo/secrets/api-key --output results/http.json
```

For native benchmarks, stop Compose first. Campaign manifests assume a reference checkout at `/srv/amd-halo/stack` and an isolated experiment root; see the [experiment guide](../experiments/README.md). Some staged experiments are unfinished and may fail their gates.

The measured firmware performance profile improved long-prompt processing by 7.6%, with little plain-decode gain. The optional `systemd/amd-halo-performance.service` is reversible; its stop action restores balanced. Measurements in this repository use that profile unless stated otherwise.

## Restore / stop

```sh
# Restore the preserved Q4_K_M / MTP-4 configuration after an experiment:
sudo docker compose -f compose.yaml -f compose.mtp.yaml up -d
# Stop inference without deleting models:
sudo docker compose -f compose.yaml -f compose.mtp.yaml down
```

Retain a separate baseline checkout and private `.env` before testing candidates. Native patches do not replace the reference runtime. No inference or host tuning runs automatically when this repository is cloned.
