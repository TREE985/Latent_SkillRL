#!/usr/bin/env bash
set -euo pipefail

cd /home/nvidia/Jiashu/SkillRL

export PYTHONPATH="/home/nvidia/Jiashu/SkillRL:${PYTHONPATH:-}"
export ALFWORLD_DATA="/home/nvidia/Jiashu/SkillRL/alfworld_data"
export OPENAI_API_KEY='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'

MODEL_NAME="${MODEL_NAME:-gpt-4o}"
ENV_NUM="${ENV_NUM:-20}"
MAX_STEPS="${MAX_STEPS:-50}"
EVAL_DATASET="${EVAL_DATASET:-eval_in_distribution}"
TEMPERATURE="${TEMPERATURE:-0.4}"
MAX_COMPLETION_TOKENS="${MAX_COMPLETION_TOKENS:-512}"
RUN_NAME="${RUN_NAME:-openai_skillbank_eval_id_n20}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is not set."
  exit 1
fi

python /home/nvidia/Jiashu/SkillRL/examples/prompt_agent/step0_eval_openai.py \
  --provider openai \
  --model "${MODEL_NAME}" \
  --env-num "${ENV_NUM}" \
  --max-steps "${MAX_STEPS}" \
  --eval-dataset "${EVAL_DATASET}" \
  --temperature "${TEMPERATURE}" \
  --max-completion-tokens "${MAX_COMPLETION_TOKENS}" \
  --run-name "${RUN_NAME}"
