# ldraw-nova-docker

> [!IMPORTANT]
> **Want to try the ldraw-nova web app? Start at the [ldraw-nova repo](https://github.com/anteloc/ldraw-nova#installation).**
>
> This repo is the Docker packaging of [ldraw-nova](https://github.com/anteloc/ldraw-nova). It turns that toolset into a web app you can run. It isn't meant to be used on its own: the Docker image is built from both repos, cloned side by side at the same tag.
>
> The project's landing page, demo video and installation steps are all in **ldraw-nova**. This README will only cover the technical side of the Docker image, and it's being rewritten.
>
> 👉 **[Go to ldraw-nova and install the web app](https://github.com/anteloc/ldraw-nova#installation)**

## Optional Sculpture model

Open **Additional settings** beside the prompt and enable **Sculpture model** to
generate a voxel sculpture with connected bricks and deterministic instruction
ordering. It uses the paired
`ldraw-nova` sculpture toolkit and the existing model cards, viewer and step player;
ordinary part-based generation remains the default. Build both companion branches
together until sculpture support is included in a matching release.

The agent saves a coloured voxel design and runs the deterministic converter through
Nova's existing tools. The result uses the normal validation, rendering, publication
and chat model-card flow, without a separate voxel-preview or visual-revision cycle.

Hover or tap the info icon for sculpture-mode help.

## Overview

COMING SOON

## Build

COMING SOON

## Configuration

COMING SOON

## Development

COMING SOON

## Acknowledgements

COMING SOON
