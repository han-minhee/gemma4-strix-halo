# Setup

Fedora 44 · AC power · `/srv/amd-halo` · [Versions](../data/software.json)

## Build & models

```sh
sudo dnf --refresh install git cmake gcc-c++ ninja-build vulkan-loader-devel \
  mesa-vulkan-drivers vulkan-tools glslc spirv-headers-devel openssl-devel \
  python3-pip moby-engine docker-cli docker-compose container-selinux
bash scripts/build.sh vulkan
python3 scripts/download.py Q4_K_M MTP --directory /srv/amd-halo/models
```

[Hashes](../versions.json) · target 18.32 GB · assistant 0.51 GB

### HIP

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

Set `.env`: `HALO_IMAGE`, `RENDER_GID`, `API_KEY_FILE`. Credentials outside Git; cache writable by container UID 1000.

```sh
sudo docker compose -f compose.yaml -f compose.mtp.yaml up -d
python3 scripts/validate_service.py --url http://127.0.0.1:8080 \
  --key-file /srv/amd-halo/secrets/api-key --output results/service-validation.json
```

API: `http://127.0.0.1:8080/v1` · `gemma-4-31b` · bearer authentication · default reasoning

## Profile

```sh
python3 scripts/http_profile.py --url http://127.0.0.1:8080 \
  --key-file /srv/amd-halo/secrets/api-key --output results/http.json
```

Native runs: stop Compose first. [Harness](../experiments/README.md).

Power: performance. Stop `amd-halo-performance.service` to restore balanced.

## Restore / stop

```sh
# Restore:
sudo docker compose -f compose.yaml -f compose.mtp.yaml up -d
# Stop:
sudo docker compose -f compose.yaml -f compose.mtp.yaml down
```

Keep the baseline checkout and private `.env` for rollback.
