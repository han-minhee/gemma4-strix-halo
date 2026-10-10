# Setup

Fedora 44 · AC power · default path: `/srv/amd-halo`. [Software versions](../data/software.json).

## Build & models

```sh
sudo dnf --refresh install git cmake gcc-c++ ninja-build vulkan-loader-devel \
  mesa-vulkan-drivers vulkan-tools glslc spirv-headers-devel openssl-devel \
  python3-pip moby-engine docker-cli docker-compose container-selinux
bash scripts/build.sh vulkan
python3 scripts/download.py Q4_K_M MTP --directory /srv/amd-halo/models
```

Runtime/model hashes: [`versions.json`](../versions.json). Target: 18.32 GB; assistant: 0.51 GB.

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

Stop Compose before native benchmarks. Reference checkout: `/srv/amd-halo/stack`. [Experiment guide](../experiments/README.md).

Benchmarks use the performance profile. `systemd/amd-halo-performance.service` applies it; stopping the unit restores balanced.

## Restore / stop

```sh
# Restore the preserved Q4_K_M / MTP-4 configuration after an experiment:
sudo docker compose -f compose.yaml -f compose.mtp.yaml up -d
# Stop inference without deleting models:
sudo docker compose -f compose.yaml -f compose.mtp.yaml down
```

Keep the baseline checkout and private `.env` for rollback.
