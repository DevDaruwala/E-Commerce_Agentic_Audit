#!/usr/bin/env bash
# Runs the Quarto that is installed in the "AI" conda environment, without
# needing `conda activate`. VS Code points to this file (see .vscode/settings.json).
ENV=/home/dev/anaconda3/envs/AI
export PATH="$ENV/bin:$PATH"
export QUARTO_DENO="$ENV/bin/deno"
export QUARTO_PANDOC="$ENV/bin/pandoc"
export QUARTO_ESBUILD="$ENV/bin/esbuild"
export QUARTO_TYPST="$ENV/bin/typst"
export QUARTO_TYPST_GATHER="$ENV/bin/typst-gather"
export QUARTO_DART_SASS="$ENV/bin/sass"
export QUARTO_SHARE_PATH="$ENV/share/quarto"
export QUARTO_CONDA_PREFIX="$ENV"
export QUARTO_PYTHON="$ENV/bin/python"
exec "$ENV/bin/quarto" "$@"
