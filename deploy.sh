#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/home/project/Option_Chain_Analysis"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend"
VENV_DIR="${BACKEND_DIR}/venv"
REMOTE="${DEPLOY_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"
BACKEND_SERVICE="option_chain_analysis.service"
FRONTEND_SERVICE="option_chain_frontend.service"
API_BASE="https://quantapi.phoneme.in/optionchain"
GUI_URL="https://quanttrade.phoneme.in/optionchain"
GUI_BASE_PATH="/optionchain"
LOCK_FILE="/run/lock/option-chain-analysis-deploy.lock"

log() {
    printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    printf '\nDeployment failed: %s\n' "$*" >&2
    exit 1
}

wait_for_url() {
    local name="$1"
    local url="$2"
    local attempts="${3:-30}"
    local delay="${4:-1}"

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if curl --fail --silent --show-error --output /dev/null "$url"; then
            printf '%s is healthy: %s\n' "$name" "$url"
            return 0
        fi
        sleep "$delay"
    done

    fail "${name} did not become healthy after ${attempts} attempts: ${url}"
}

[[ "${EUID}" -eq 0 ]] || fail "run this script as root"
[[ -d "${APP_DIR}/.git" ]] || fail "Git repository not found at ${APP_DIR}"
[[ -f "${BACKEND_DIR}/.env" ]] || fail "missing ${BACKEND_DIR}/.env"

for command_name in git python3 npm curl systemctl nginx flock; do
    command -v "$command_name" >/dev/null 2>&1 ||
        fail "required command is not installed: ${command_name}"
done

exec 9>"${LOCK_FILE}"
flock -n 9 || fail "another deployment is already running"

cd "${APP_DIR}"

if ! git diff --quiet || ! git diff --cached --quiet; then
    fail "tracked files have uncommitted changes; commit or discard them before deploying"
fi

log "Fetching ${REMOTE}/${BRANCH}"
git fetch --prune "${REMOTE}" "${BRANCH}"

git show-ref --verify --quiet "refs/heads/${BRANCH}" ||
    git branch "${BRANCH}" "${REMOTE}/${BRANCH}"
git switch "${BRANCH}"
git pull --ff-only "${REMOTE}" "${BRANCH}"

DEPLOYED_COMMIT="$(git rev-parse HEAD)"
printf 'Deploying commit %s\n' "${DEPLOYED_COMMIT}"

log "Installing backend dependencies"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
fi
"${VENV_DIR}/bin/python" -m pip install \
    --disable-pip-version-check \
    --requirement "${BACKEND_DIR}/requirements.txt"

if [[ "${RUN_TESTS:-1}" == "1" ]]; then
    log "Running backend tests"
    (
        cd "${BACKEND_DIR}"
        "${VENV_DIR}/bin/python" -m pytest -q
    )
else
    log "Skipping backend tests because RUN_TESTS=${RUN_TESTS:-0}"
fi

log "Installing frontend dependencies"
(
    cd "${FRONTEND_DIR}"
    npm ci
)

log "Building frontend"
(
    cd "${FRONTEND_DIR}"
    NEXT_PUBLIC_BASE_PATH="${GUI_BASE_PATH}" \
        NEXT_PUBLIC_API_BASE="${API_BASE}" \
        npm run build
)

log "Validating Nginx configuration"
nginx -t

log "Restarting application services"
systemctl daemon-reload
systemctl restart "${BACKEND_SERVICE}"
systemctl restart "${FRONTEND_SERVICE}"

systemctl is-active --quiet "${BACKEND_SERVICE}" ||
    fail "${BACKEND_SERVICE} failed to start"
systemctl is-active --quiet "${FRONTEND_SERVICE}" ||
    fail "${FRONTEND_SERVICE} failed to start"

log "Checking local services"
wait_for_url "Backend" "http://127.0.0.1:8500/health"
wait_for_url "Frontend" "http://127.0.0.1:8600/optionchain"

log "Checking public routes"
wait_for_url "Public API" "${API_BASE}/health"
wait_for_url "Public GUI" "${GUI_URL}"

log "Deployment completed"
printf 'Commit: %s\nAPI: %s\nGUI: %s\n' \
    "${DEPLOYED_COMMIT}" "${API_BASE}" "${GUI_URL}"
