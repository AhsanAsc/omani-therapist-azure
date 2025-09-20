export RG="Arabic_therapist"
export LOCATION="uaenorth"
export ACR_NAME="omanitherapistreg"
export ENV_NAME="managedEnvironment-Arabictherapist-990c"
export APP_NAME="omani-therapist"
export ACR_NAME="omanitherapistreg"

export AZURE_SPEECH_KEY="<paste-at-runtime-or-use-key-vault>"
export OPENAI_API_KEY="<paste-at-runtime-or-use-key-vault>"
export AZURE_SPEECH_REGION="uaenorth"
export VOICE_AR="ar-OM-AyshaNeural"
export VOICE_EN="en-US-JennyNeural"

export IMAGE_TAG=$(date +%Y%m%d-%H%M%S)
export IMAGE_NAME="${ACR_NAME}.azurecr.io/omani-therapist:${IMAGE_TAG}"

echo "RG=[$RG]"
echo "ACR_NAME=[$ACR_NAME]"
echo ENV_NAME=$ENV_NAME
echo APP_NAME=$APP_NAME
echo IMAGE_NAME=$IMAGE_NAME

ACR_LOGIN=$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)
IMAGE_TAG="241502b"
IMAGE="$ACR_LOGIN/omani-therapist:$IMAGE_TAG"
