#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIOS_DIR="$ROOT_DIR/infrastructure/finding-scenarios"
STACK_DIR="$SCENARIOS_DIR/stacks/cspm_insecure_bundle"

export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.terraform.d/plugin-cache}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"

AWS_PROVIDER_ROOT="$TF_PLUGIN_CACHE_DIR/registry.terraform.io/hashicorp/aws"
if [[ -n "$(find "$AWS_PROVIDER_ROOT" -type f -name 'terraform-provider-aws_v*_x5' -print -quit 2>/dev/null)" ]]; then
  TF_CLI_CONFIG_FILE="$(mktemp)"
  cat >"$TF_CLI_CONFIG_FILE" <<EOF
provider_installation {
  filesystem_mirror {
    path    = "$TF_PLUGIN_CACHE_DIR"
    include = ["registry.terraform.io/hashicorp/aws"]
  }
  direct {
    exclude = ["registry.terraform.io/hashicorp/aws"]
  }
}
EOF
  export TF_CLI_CONFIG_FILE
  trap 'rm -f "$TF_CLI_CONFIG_FILE"' EXIT
  echo "Using local provider mirror from: $TF_PLUGIN_CACHE_DIR"
else
  echo "No local aws provider mirror found under $AWS_PROVIDER_ROOT; terraform may need registry access."
fi

echo "Using Terraform plugin cache: $TF_PLUGIN_CACHE_DIR"

for dir in "$SCENARIOS_DIR"/*; do
  if [[ -d "$dir" && -f "$dir/main.tf" ]]; then
    echo "Initializing $(basename "$dir")"
    terraform -chdir="$dir" init
  fi
done

if [[ -f "$STACK_DIR/main.tf" ]]; then
  echo "Initializing $(basename "$STACK_DIR")"
  terraform -chdir="$STACK_DIR" init
fi

echo "Done. Providers are cached and reused across scenarios."
