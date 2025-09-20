# ===== Azure resource naming =====
export RG="omani-therapist-rg"
export LOCATION="uaenorth"
export ACR_NAME="omanitherapyacr"
export APP_NAME="omani-therapist"

# ===== Container image =====
export IMAGE_TAG="v1"
export IMAGE_NAME="$ACR_NAME.azurecr.io/$APP_NAME:$IMAGE_TAG"

# ===== Azure Speech =====
export AZURE_SPEECH_REGION="uae-north"
export AZURE_SPEECH_KEY="<paste-at-runtime-or-use-key-vault>"

# ===== OpenAI (or Azure OpenAI) =====
export OPENAI_API_KEY="<paste-at-runtime-or-use-key-vault>"

# ===== Voices =====
export VOICE_AR="ar-OM-AyshaNeural"
export VOICE_EN="en-US-JennyNeural"

# ===== App runtime flags =====
export SECURE_MODE="true"
export REDACT_LOGS="true"

# ===== GitHub (optional – for GH Actions to know your ACR) =====
export GH_CONTAINER_REGISTRY="$ACR_NAME.azurecr.io"

echo "Loaded vars: RG=$RG, ACR=$ACR_NAME, APP=$APP_NAME, LOCATION=$LOCATION, IMAGE=$IMAGE_NAME"
