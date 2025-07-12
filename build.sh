#!/usr/bin/env bash
export repository=ghcr.io/dekeyrej
export tag=latest
export BUILDX_BUILDER=container

docker buildx build --platform linux/amd64 --tag ${repository}/apiserver:${tag} --push .

# docker buildx build --platform linux/amd64,linux/arm64 --build-arg MICROSERVICE=${i} --tag ${repository}/${i}:${tag} --push .

# docker buildx build --build-arg MICROSERVICE=events --tag ghcr.io/dekeyrej/events:latest --push .
# BUILDX_BUILDER=container docker buildx build --platform linux/amd64,linux/arm64 --build-arg MICROSERVICE=events --tag ghcr.io/dekeyrej/events:latest --push .
# buildctl build --frontend dockerfile.v0 --local context=. --local dockerfile=. --opt build-arg:MICROSERVICE=${i} --output type=image,name=${repository}/${i}:${tag},registry.insecure=true,push=true