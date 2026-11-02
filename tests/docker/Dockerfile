# Real-AFNI test image for tests/test_real_afni.py.
#
# Mirrors cloudpipe's images/fmri-first-level-proc base (ubuntu:26.04, same apt set,
# same pinned AFNI_26.3.07 tarball digests for amd64 and arm64), so the formats tested
# here are the ones production sees; cloudpipe's first-level pods run the arm64 build.
# The repository is mounted at run time, not baked in:
#
#   docker build -t fflp-afni:26.3.07 tests/docker
#   docker run --rm -v "$PWD":/src:ro -w /tmp fflp-afni:26.3.07 \
#       pytest /src/tests -m afni -p no:cacheprovider
#
# AFNI's tarballs are unversioned and roll in place. When NIMH rolls this one the
# digest check fails; bump AFNI_VERSION, both AFNI_SHA256_* digests, and the AFNI pin
# in src/fmri_first_level_proc/data/tools.lock.yaml together.
FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 curl tcsh bc gsl-bin netpbm libglib2.0-0 libgomp1 libxm4 libxpm4 libxt6 \
    libjpeg62 libglu1-mesa libglw1-mesa-dev libssl-dev libcurl4-openssl-dev libxml2-dev \
    ca-certificates libfontconfig1 libxrender1 \
    python3 python3-venv \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# TARGETARCH is set by BuildKit. The amd64 and arm64 builds are different files with
# different digests (same values as cloudpipe's image).
ARG TARGETARCH
ARG AFNI_VERSION=AFNI_26.3.07
ARG AFNI_SHA256_AMD64=a65d5dd466830de2e222bc305020e23b29de45dc677b26a1e6ce2a0f0c44ea6d
ARG AFNI_SHA256_ARM64=9391701ed9fe81d5ddf2c19ab250eef53f301767150289c8d3914ab60dfc97c6
# The download is large and the server drops connections; retry with resume.
RUN set -eu; \
    case "${TARGETARCH}" in \
      amd64) url=linux_ubuntu_24_64.tgz;  want="${AFNI_SHA256_AMD64}" ;; \
      arm64) url=linux_ubuntu_24_ARM.tgz; want="${AFNI_SHA256_ARM64}" ;; \
      *) echo "unsupported TARGETARCH '${TARGETARCH}'"; exit 1 ;; \
    esac; \
    for i in 1 2 3 4 5 6; do \
      curl -fsSL --retry 5 --retry-all-errors -C - -o /tmp/afni.tgz \
        "https://afni.nimh.nih.gov/pub/dist/tgz/${url}" && break; \
      echo "download attempt $i failed; resuming"; sleep 5; \
    done; \
    got=$(sha256sum /tmp/afni.tgz | cut -d' ' -f1); \
    if [ "${got}" != "${want}" ]; then echo "AFNI digest mismatch (${TARGETARCH}): ${got}"; exit 1; fi; \
    mkdir -p /opt/afni; tar xzf /tmp/afni.tgz -C /opt/afni --strip-components=1; rm -f /tmp/afni.tgz; \
    ver=$(sed -n 1p /opt/afni/AFNI_version.txt); \
    if [ "${ver}" != "${AFNI_VERSION}" ]; then echo "tarball is ${ver}"; exit 1; fi

RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir numpy pandas pyyaml pytest
ENV PATH="/opt/afni:/opt/venv/bin:$PATH" \
    PYTHONPATH=/src/src:/src/tests \
    AFNI_NOSPLASH=YES AFNI_ENVIRON_WARNINGS=NO
WORKDIR /work
