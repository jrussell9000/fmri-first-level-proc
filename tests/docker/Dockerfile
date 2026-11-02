# Real-AFNI test image for tests/test_real_afni.py.
#
# Mirrors cloudpipe's images/fmri-first-level-proc base (ubuntu:26.04, same apt set,
# same pinned AFNI_26.3.07 amd64 tarball digest), so the formats tested here are the
# ones production sees. The repository is mounted at run time, not baked in:
#
#   docker build -t fflp-afni:26.3.07 tests/docker
#   docker run --rm -v "$PWD":/src:ro -w /tmp fflp-afni:26.3.07 \
#       pytest /src/tests -m afni -p no:cacheprovider
#
# AFNI's tarballs are unversioned and roll in place. When NIMH rolls this one the
# digest check fails; bump AFNI_VERSION, AFNI_SHA256, and the AFNI pin in
# src/fmri_first_level_proc/data/tools.lock.yaml together.
FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 curl tcsh bc gsl-bin netpbm libglib2.0-0 libgomp1 libxm4 libxpm4 libxt6 \
    libjpeg62 libglu1-mesa libglw1-mesa-dev libssl-dev libcurl4-openssl-dev libxml2-dev \
    ca-certificates libfontconfig1 libxrender1 \
    python3 python3-venv \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG AFNI_VERSION=AFNI_26.3.07
ARG AFNI_SHA256=a65d5dd466830de2e222bc305020e23b29de45dc677b26a1e6ce2a0f0c44ea6d
# The download is large and the server drops connections; retry with resume.
RUN set -eu; \
    for i in 1 2 3 4 5 6; do \
      curl -fsSL --retry 5 --retry-all-errors -C - -o /tmp/afni.tgz \
        https://afni.nimh.nih.gov/pub/dist/tgz/linux_ubuntu_24_64.tgz && break; \
      echo "download attempt $i failed; resuming"; sleep 5; \
    done; \
    got=$(sha256sum /tmp/afni.tgz | cut -d' ' -f1); \
    if [ "${got}" != "${AFNI_SHA256}" ]; then echo "AFNI digest mismatch: ${got}"; exit 1; fi; \
    mkdir -p /opt/afni; tar xzf /tmp/afni.tgz -C /opt/afni --strip-components=1; rm -f /tmp/afni.tgz; \
    ver=$(sed -n 1p /opt/afni/AFNI_version.txt); \
    if [ "${ver}" != "${AFNI_VERSION}" ]; then echo "tarball is ${ver}"; exit 1; fi

RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir numpy pandas pyyaml pytest
ENV PATH="/opt/afni:/opt/venv/bin:$PATH" \
    PYTHONPATH=/src/src:/src/tests \
    AFNI_NOSPLASH=YES AFNI_ENVIRON_WARNINGS=NO
WORKDIR /work
