#!/usr/bin/env bash
set -euo pipefail

EXECUTION_ROOT="executable/actions"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required but not installed."
  exit 1
fi

CACHE_ROOT="${HOME}/.aws-security-autopilot/terraform"
mkdir -p "${CACHE_ROOT}/plugin-cache" "${CACHE_ROOT}/provider-mirror"
export TF_PLUGIN_CACHE_DIR="${CACHE_ROOT}/plugin-cache"
export TF_PROVIDER_MIRROR_DIR="${CACHE_ROOT}/provider-mirror"
PREFERRED_TF_PROVIDER_MIRROR_DIR="${HOME}/.terraform.d/plugin-cache"
ACTIVE_TF_PROVIDER_MIRROR_DIR="${TF_PROVIDER_MIRROR_DIR}"
export TF_REGISTRY_CLIENT_TIMEOUT="${TF_REGISTRY_CLIENT_TIMEOUT:-30}"
export TF_REGISTRY_DISCOVERY_RETRY="${TF_REGISTRY_DISCOVERY_RETRY:-3}"

TFRC_PATH="${CACHE_ROOT}/terraformrc"
write_tfrc_with_cache_only() {
  cat > "${TFRC_PATH}" <<EOF
plugin_cache_dir = "${TF_PLUGIN_CACHE_DIR}"
EOF
}

write_tfrc_with_mirror() {
  local mirror_dir="$1"
  cat > "${TFRC_PATH}" <<EOF
provider_installation {
  filesystem_mirror {
    path    = "${mirror_dir}"
    include = ["registry.terraform.io/hashicorp/aws"]
  }
  direct {
    exclude = ["registry.terraform.io/hashicorp/aws"]
  }
}
EOF
}

export TF_CLI_CONFIG_FILE="${TFRC_PATH}"

AWS_PROVIDER_VERSION="5.100.0"
AWS_PROVIDER_LOCKFILE="${CACHE_ROOT}/.aws-provider-${AWS_PROVIDER_VERSION}.lock.hcl"
TERRAFORM_PROVIDER_OS="$(uname | tr '[:upper:]' '[:lower:]')"
TERRAFORM_PROVIDER_ARCH="$(uname -m)"
case "${TERRAFORM_PROVIDER_ARCH}" in
  x86_64)
    TERRAFORM_PROVIDER_ARCH="amd64"
    ;;
  aarch64|arm64)
    TERRAFORM_PROVIDER_ARCH="arm64"
    ;;
esac
TERRAFORM_PROVIDER_PLATFORM="${TERRAFORM_PROVIDER_OS}_${TERRAFORM_PROVIDER_ARCH}"

has_cached_aws_provider() {
  find -L "${TF_PLUGIN_CACHE_DIR}/registry.terraform.io/hashicorp/aws/${AWS_PROVIDER_VERSION}" -type f -name 'terraform-provider-aws_v*_x5' -print -quit 2>/dev/null | grep -q .
}

has_mirrored_aws_provider() {
  local mirror_dir="${1:-${ACTIVE_TF_PROVIDER_MIRROR_DIR}}"
  find -L "${mirror_dir}/registry.terraform.io/hashicorp/aws/${AWS_PROVIDER_VERSION}" -type f -print -quit 2>/dev/null | grep -q .
}

has_preferred_mirrored_aws_provider() {
  has_mirrored_aws_provider "${PREFERRED_TF_PROVIDER_MIRROR_DIR}"
}

bootstrap_provider_cache() {
  local bootstrap_dir marker
  marker="${CACHE_ROOT}/.aws-provider-${AWS_PROVIDER_VERSION}.ready"
  ACTIVE_TF_PROVIDER_MIRROR_DIR="${TF_PROVIDER_MIRROR_DIR}"
  if has_preferred_mirrored_aws_provider; then
    ACTIVE_TF_PROVIDER_MIRROR_DIR="${PREFERRED_TF_PROVIDER_MIRROR_DIR}"
  fi
  if [ -f "${marker}" ] && has_mirrored_aws_provider "${ACTIVE_TF_PROVIDER_MIRROR_DIR}" && [ -s "${AWS_PROVIDER_LOCKFILE}" ]; then
    return 0
  fi
  bootstrap_dir=$(mktemp -d)
  cat > "${bootstrap_dir}/versions.tf" <<'EOF'
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
  }
}
EOF

  if [ "${ACTIVE_TF_PROVIDER_MIRROR_DIR}" = "${PREFERRED_TF_PROVIDER_MIRROR_DIR}" ]; then
    (
      cd "${bootstrap_dir}"
      terraform providers lock -fs-mirror="${ACTIVE_TF_PROVIDER_MIRROR_DIR}" -platform="${TERRAFORM_PROVIDER_PLATFORM}" >/dev/null
      cp .terraform.lock.hcl "${AWS_PROVIDER_LOCKFILE}"
    )
  else
    (
      cd "${bootstrap_dir}"
      env -u TF_CLI_CONFIG_FILE -u TF_PLUGIN_CACHE_DIR -u TF_PROVIDER_MIRROR_DIR terraform providers mirror "${ACTIVE_TF_PROVIDER_MIRROR_DIR}" >/dev/null
      terraform providers lock -fs-mirror="${ACTIVE_TF_PROVIDER_MIRROR_DIR}" -platform="${TERRAFORM_PROVIDER_PLATFORM}" >/dev/null
      cp .terraform.lock.hcl "${AWS_PROVIDER_LOCKFILE}"
    )
  fi
  rm -rf "${bootstrap_dir}"
  touch "${marker}"
}

seed_canonical_aws_lockfile() {
  local dir="$1"
  if [ ! -s "${AWS_PROVIDER_LOCKFILE}" ]; then
    echo "ERROR: canonical AWS provider lockfile is missing at ${AWS_PROVIDER_LOCKFILE}."
    return 1
  fi
  rm -rf "$dir/.terraform"
  cp "${AWS_PROVIDER_LOCKFILE}" "$dir/.terraform.lock.hcl"
}

collect_action_dirs() {
  local dir
  while IFS= read -r dir; do
    if find "$dir" -maxdepth 1 -name '*.tf' -print -quit 2>/dev/null | grep -q .; then
      ACTION_DIRS+=("$dir")
    fi
  done < <(find "${EXECUTION_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
}

is_known_duplicate_only() {
  local log_file="$1"
  local duplicate_pattern
  duplicate_pattern='InvalidPermission\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists'

  if ! grep -Eiq "$duplicate_pattern" "$log_file"; then
    return 1
  fi
  if grep -Eiq 'AccessDenied|UnauthorizedOperation|InvalidGroupId|DependencyViolation|Throttl|ExpiredToken|not found|NoSuch' "$log_file"; then
    return 1
  fi
  return 0
}

apply_with_duplicate_tolerance() {
  local dir="$1"
  local log_file rc resource existing_id duplicate_line

  log_file=$(mktemp)
  set +e
  (
    cd "$dir"
    terraform apply -auto-approve
  ) >"$log_file" 2>&1
  rc=$?
  set -e
  cat "$log_file"

  if [ "$rc" -eq 0 ]; then
    rm -f "$log_file"
    return 0
  fi

  if is_known_duplicate_only "$log_file"; then
    resource=$(sed -n 's/.*with \([^,]*\),/\1/p' "$log_file" | head -n 1)
    existing_id=$(grep -Eo 'sg-[0-9A-Za-z-]+' "$log_file" | head -n 1)
    duplicate_line=$(grep -Ei 'InvalidPermission\.Duplicate|already exists|AlreadyExists|EntityAlreadyExists' "$log_file" | head -n 1)
    echo "WARNING: duplicate/already-existing resource detected; continuing without failure."
    echo "  action: $dir"
    if [ -n "$resource" ]; then
      echo "  resource: $resource"
    fi
    if [ -n "$existing_id" ]; then
      echo "  existing identifier: $existing_id"
    fi
    if [ -n "$duplicate_line" ]; then
      echo "  detail: $duplicate_line"
    fi
    rm -f "$log_file"
    return 0
  fi

  rm -f "$log_file"
  return "$rc"
}

run_terraform_init_with_retry() {
  local dir="$1"
  local attempts=5
  local attempt=1
  local sleep_seconds=3
  local rc=0

  while [ "$attempt" -le "$attempts" ]; do
    if ! seed_canonical_aws_lockfile "$dir"; then
      return 1
    fi
    set +e
    (
      cd "$dir"
      terraform init -input=false -lockfile=readonly
    )
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -lt "$attempts" ]; then
      echo "WARNING: terraform init failed for $dir (attempt $attempt/$attempts). Retrying in ${sleep_seconds}s..."
      sleep "$sleep_seconds"
      sleep_seconds=$((sleep_seconds * 2))
      if [ "$sleep_seconds" -gt 30 ]; then
        sleep_seconds=30
      fi
    fi
    attempt=$((attempt + 1))
  done

  return "$rc"
}

has_unresolved_placeholders() {
  local dir="$1"
  local placeholders
  placeholders=$(grep -R -n --include='*.tf' -E 'REPLACE_[A-Z0-9_]+' "$dir" 2>/dev/null || true)
  if [ -n "$placeholders" ]; then
    echo "ERROR: unresolved placeholder token(s) found in Terraform files for $dir:"
    echo "$placeholders"
    return 0
  fi
  return 1
}

bootstrap_provider_cache
write_tfrc_with_mirror "${ACTIVE_TF_PROVIDER_MIRROR_DIR}"

ACTION_DIRS=()
collect_action_dirs
TOTAL="${#ACTION_DIRS[@]}"
if [ "${TOTAL:-0}" -eq 0 ]; then
  echo "No executable Terraform action folders found under ${EXECUTION_ROOT}/."
  exit 0
fi

SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_ACTIONS=()

for dir in "${ACTION_DIRS[@]}"; do
  echo ""
  echo "=== Running terraform in $dir ==="

  if has_unresolved_placeholders "$dir"; then
    echo "ERROR: unresolved placeholders detected for $dir. Skipping this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (precheck)")
    continue
  fi

  if ! run_terraform_init_with_retry "$dir"; then
    echo "ERROR: terraform init failed for $dir after retries. Skipping this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (init)")
    continue
  fi

  set +e
  (
    cd "$dir"
    terraform plan -input=false
  )
  plan_rc=$?
  set -e
  if [ "$plan_rc" -ne 0 ]; then
    echo "ERROR: terraform plan failed for $dir. Skipping apply for this action folder."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (plan)")
    continue
  fi

  if ! apply_with_duplicate_tolerance "$dir"; then
    echo "ERROR: terraform apply failed for $dir. Continuing with remaining action folders."
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_ACTIONS+=("$dir (apply)")
    continue
  fi

  SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
done

echo "Bundle run completed."
echo "  Successful action folders: ${SUCCESS_COUNT}/${TOTAL}"
echo "  Failed action folders: ${FAILED_COUNT}/${TOTAL}"
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "Failed folders summary:"
  for failed in "${FAILED_ACTIONS[@]}"; do
    echo "  - $failed"
  done
  exit 1
fi
echo "All action folders completed successfully."
