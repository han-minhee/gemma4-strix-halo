ARG BASE_IMAGE=fedora@sha256:be9d65e2344d805cc11114319c685ecaa96b6d9b4350a0a6460cdb931babbd19
FROM ${BASE_IMAGE}
ARG BACKEND=vulkan
RUN dnf --setopt=install_weak_deps=False --setopt=max_parallel_downloads=16 \
    --setopt=fedora.metalink= \
    --setopt=fedora.baseurl=https://ftp.kaist.ac.kr/fedora/linux/releases/44/Everything/x86_64/os/ \
    --setopt=updates.metalink= \
    --setopt=updates.baseurl=https://ftp.kaist.ac.kr/fedora/linux/updates/44/Everything/x86_64/ install -y \
    mesa-vulkan-drivers vulkan-loader libgomp libatomic libstdc++ curl-minimal \
    numactl-libs libdrm elfutils-libelf libzstd && dnf clean all
COPY .runtime/build-${BACKEND}/bin/ /opt/llama/bin/
ENV LD_LIBRARY_PATH=/opt/llama/bin
EXPOSE 8080
ENTRYPOINT ["/opt/llama/bin/llama-server"]
