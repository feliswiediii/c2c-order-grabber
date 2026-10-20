#!/bin/bash
#
# RTT Benchmark Deployment Script for AWS Lightsail
#
# This script automates the deployment of RTT measurement containers
# to multiple AWS regions using Lightsail Container Service.
#
# Usage:
#   ./deploy_benchmark.sh [regions...]
#
# Examples:
#   ./deploy_benchmark.sh                           # All regions
#   ./deploy_benchmark.sh us-east-1 eu-west-1       # Specific regions
#

set -euo pipefail

# Configuration
DOCKER_IMAGE="rtt-benchmark"
DOCKER_TAG="latest"
SERVICE_NAME_PREFIX="rtt-benchmark"
CONTAINER_NAME="benchmark"

# AWS Lightsail regions supporting container services
# https://lightsail.aws.amazon.com/ls/docs/en_us/articles/amazon-lightsail-container-services
AVAILABLE_REGIONS=(
    "us-east-1"       # Virginia
    "us-west-2"       # Oregon
    "eu-west-1"       # Ireland
    "eu-central-1"    # Frankfurt
    "eu-north-1"      # Stockholm
    "ap-southeast-1"  # Singapore
    "ap-northeast-1"  # Tokyo
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get regions from command line or use all
if [ $# -gt 0 ]; then
    REGIONS=("$@")
else
    REGIONS=("${AVAILABLE_REGIONS[@]}")
fi

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    log_error "AWS CLI not found. Please install: https://aws.amazon.com/cli/"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    log_error "Docker not found. Please install: https://www.docker.com/"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_warning "jq not found. Installing for JSON parsing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq || log_error "Failed to install jq. Please install manually."
    else
        log_error "Please install jq manually: https://stedolan.github.io/jq/"
        exit 1
    fi
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi

log_success "Prerequisites check passed"
echo

# Build Docker image
log_info "Building Docker image..."
cd "$(dirname "$0")"

if ! docker buildx build --platform linux/amd64 -t "${DOCKER_IMAGE}:${DOCKER_TAG}" .; then
    log_error "Docker build failed"
    exit 1
fi

log_success "Docker image built: ${DOCKER_IMAGE}:${DOCKER_TAG}"
echo

# Results storage
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="${RESULTS_DIR}/rtt_results_${TIMESTAMP}.json"

echo "{" > "$RESULTS_FILE"
echo '  "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",' >> "$RESULTS_FILE"
echo '  "regions": {' >> "$RESULTS_FILE"

FIRST_REGION=true

# Deploy to each region
for REGION in "${REGIONS[@]}"; do
    echo
    log_info "================================================"
    log_info "Region: $REGION"
    log_info "================================================"

    SERVICE_NAME="${SERVICE_NAME_PREFIX}-${REGION}"

    # Step 1: Create container service
    log_info "Creating Lightsail container service in $REGION..."

    # Check if service already exists
    if aws lightsail get-container-services --region "$REGION" --service-name "$SERVICE_NAME" &> /dev/null; then
        log_warning "Service $SERVICE_NAME already exists. Deleting..."
        aws lightsail delete-container-service --region "$REGION" --service-name "$SERVICE_NAME" || true
        sleep 10
    fi

    # Create service (nano tier - cheapest)
    if ! aws lightsail create-container-service \
        --region "$REGION" \
        --service-name "$SERVICE_NAME" \
        --power nano \
        --scale 1 \
        --tags key=Purpose,value=RTT-Benchmark \
        &> /dev/null; then
        log_error "Failed to create service in $REGION"
        continue
    fi

    log_success "Service created: $SERVICE_NAME"

    # Step 2: Wait for service to be ready
    log_info "Waiting for service to be ready (this may take 2-3 minutes)..."

    for i in {1..60}; do
        STATE=$(aws lightsail get-container-services \
            --region "$REGION" \
            --service-name "$SERVICE_NAME" \
            --query 'containerServices[0].state' \
            --output text 2>/dev/null || echo "PENDING")

        if [ "$STATE" == "READY" ]; then
            log_success "Service is READY"
            break
        fi

        echo -n "."
        sleep 5

        if [ $i -eq 60 ]; then
            log_error "Timeout waiting for service to be ready"
            continue 2
        fi
    done
    echo

    # Step 3: Push Docker image to service
    log_info "Pushing Docker image to Lightsail..."

    PUSH_OUTPUT=$(aws lightsail push-container-image \
        --region "$REGION" \
        --service-name "$SERVICE_NAME" \
        --label "$CONTAINER_NAME" \
        --image "${DOCKER_IMAGE}:${DOCKER_TAG}" 2>&1) || {
        log_error "Failed to push image"
        echo "$PUSH_OUTPUT"
        continue
    }

    # Extract image reference from push output
    IMAGE_REF=$(echo "$PUSH_OUTPUT" | grep -oE ':[^/]+\.'${SERVICE_NAME}'\.'${CONTAINER_NAME}'\.[0-9]+' | head -1)

    if [ -z "$IMAGE_REF" ]; then
        log_error "Failed to extract image reference"
        echo "$PUSH_OUTPUT"
        continue
    fi

    log_success "Image pushed: $IMAGE_REF"

    # Step 4: Create deployment
    log_info "Creating deployment..."

    DEPLOYMENT_CONFIG=$(cat <<EOF
{
  "containers": {
    "$CONTAINER_NAME": {
      "image": "$IMAGE_REF",
      "command": [],
      "environment": {},
      "ports": {}
    }
  },
  "publicEndpoint": null
}
EOF
)

    if ! aws lightsail create-container-service-deployment \
        --region "$REGION" \
        --service-name "$SERVICE_NAME" \
        --cli-input-json "$DEPLOYMENT_CONFIG" \
        &> /dev/null; then
        log_error "Failed to create deployment"
        continue
    fi

    log_success "Deployment created"

    # Step 5: Wait for deployment to complete
    log_info "Waiting for deployment to complete..."

    for i in {1..60}; do
        DEPLOY_STATE=$(aws lightsail get-container-services \
            --region "$REGION" \
            --service-name "$SERVICE_NAME" \
            --query 'containerServices[0].currentDeployment.state' \
            --output text 2>/dev/null || echo "ACTIVATING")

        if [ "$DEPLOY_STATE" == "ACTIVE" ]; then
            log_success "Deployment is ACTIVE"
            break
        fi

        echo -n "."
        sleep 5

        if [ $i -eq 60 ]; then
            log_error "Timeout waiting for deployment"
            continue 2
        fi
    done
    echo

    # Step 6: Wait for container to run and collect logs
    log_info "Waiting for benchmark to complete (30 seconds)..."
    sleep 30

    # Step 7: Get logs
    log_info "Retrieving benchmark results..."

    LOGS=$(aws lightsail get-container-log \
        --region "$REGION" \
        --service-name "$SERVICE_NAME" \
        --container-name "$CONTAINER_NAME" \
        --output text 2>/dev/null || echo "")

    if [ -z "$LOGS" ]; then
        log_warning "No logs available yet. Waiting 30 more seconds..."
        sleep 30
        LOGS=$(aws lightsail get-container-log \
            --region "$REGION" \
            --service-name "$SERVICE_NAME" \
            --container-name "$CONTAINER_NAME" \
            --output text 2>/dev/null || echo "")
    fi

    # Extract JSON output from logs
    JSON_OUTPUT=$(echo "$LOGS" | sed -n '/^{/,/^}/p' | jq -c '.' 2>/dev/null || echo "{}")

    # Save logs to file
    LOG_FILE="${RESULTS_DIR}/logs_${REGION}_${TIMESTAMP}.txt"
    echo "$LOGS" > "$LOG_FILE"

    if [ "$JSON_OUTPUT" != "{}" ]; then
        log_success "Benchmark completed successfully"

        # Extract key metrics
        RTT=$(echo "$JSON_OUTPUT" | jq -r '.estimated_rtt_ms // 0')
        MEDIAN_TCP=$(echo "$JSON_OUTPUT" | jq -r '.tcp_handshake.median // 0')
        MEDIAN_HTTP=$(echo "$JSON_OUTPUT" | jq -r '.http_request.median // 0')

        echo "   RTT:         ${RTT}ms"
        echo "   TCP median:  ${MEDIAN_TCP}ms"
        echo "   HTTP median: ${MEDIAN_HTTP}ms"

        # Add to results JSON
        if [ "$FIRST_REGION" = true ]; then
            FIRST_REGION=false
        else
            echo "," >> "$RESULTS_FILE"
        fi

        echo "    \"$REGION\": $JSON_OUTPUT" >> "$RESULTS_FILE"
    else
        log_error "Failed to extract benchmark results"
        echo "Logs saved to: $LOG_FILE"
    fi

    # Step 8: Cleanup - delete service
    log_info "Cleaning up: deleting service..."

    aws lightsail delete-container-service \
        --region "$REGION" \
        --service-name "$SERVICE_NAME" \
        &> /dev/null || log_warning "Failed to delete service (may need manual cleanup)"

    log_success "Service deleted"
done

# Finalize results JSON
echo >> "$RESULTS_FILE"
echo '  }' >> "$RESULTS_FILE"
echo '}' >> "$RESULTS_FILE"

# Print summary
echo
echo
log_info "================================================"
log_info "BENCHMARK SUMMARY"
log_info "================================================"
echo

if [ -f "$RESULTS_FILE" ] && jq empty "$RESULTS_FILE" 2>/dev/null; then
    echo "📊 RTT Results by Region:"
    echo
    printf "%-20s %10s %10s %10s %10s\n" "Region" "RTT (ms)" "TCP (ms)" "TLS (ms)" "HTTP (ms)"
    echo "--------------------------------------------------------------------------------"

    for REGION in "${REGIONS[@]}"; do
        if jq -e ".regions.\"$REGION\"" "$RESULTS_FILE" &> /dev/null; then
            RTT=$(jq -r ".regions.\"$REGION\".estimated_rtt_ms // 0" "$RESULTS_FILE")
            TCP=$(jq -r ".regions.\"$REGION\".tcp_handshake.median // 0" "$RESULTS_FILE")
            TLS=$(jq -r ".regions.\"$REGION\".tls_handshake.median // 0" "$RESULTS_FILE")
            HTTP=$(jq -r ".regions.\"$REGION\".http_request.median // 0" "$RESULTS_FILE")

            printf "%-20s %9.1fms %9.1fms %9.1fms %9.1fms\n" "$REGION" "$RTT" "$TCP" "$TLS" "$HTTP"
        fi
    done

    echo
    echo "📁 Full results saved to: $RESULTS_FILE"

    # Find best region
    BEST_REGION=$(jq -r '.regions | to_entries | min_by(.value.estimated_rtt_ms) | .key' "$RESULTS_FILE" 2>/dev/null || echo "N/A")
    BEST_RTT=$(jq -r ".regions.\"$BEST_REGION\".estimated_rtt_ms // 0" "$RESULTS_FILE" 2>/dev/null)

    echo
    log_success "🏆 Best region: $BEST_REGION (RTT: ${BEST_RTT}ms)"
else
    log_error "No valid results generated"
fi

echo
log_info "Benchmark complete!"
