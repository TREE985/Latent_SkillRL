# Step-0 Eval Commands

This file stores the current step-0 evaluation commands and parameter defaults for ALFWorld prompt-agent evaluation.

## Current Default Model

- HF model path: `/mnt/agent-project/ckpts/Alfworld-7B-SFT-hf`
- Project root: `/home/nvidia/Jiashu/SkillRL`
- Local eval save dir: `/home/nvidia/Jiashu/SkillRL/logs/step0_eval_local`
- OpenAI eval save dir: `/home/nvidia/Jiashu/SkillRL/logs/step0_eval_openai`
- ALFWorld data dir: `/home/nvidia/Jiashu/SkillRL/alfworld_data`
- Skills JSON: `/home/nvidia/Jiashu/SkillRL/memory_data/alfworld/claude_style_skills.json`

## 1. Recommended: Local HF Model Eval

This is the main command path for the current local model.

### 1.1 Run through the shell wrapper

```bash
nohup bash -lc '
cd /home/nvidia/Jiashu/SkillRL
PYTHONPATH=/home/nvidia/Jiashu/SkillRL:${PYTHONPATH:-} \
ALFWORLD_DATA=/home/nvidia/Jiashu/SkillRL/alfworld_data \
CUDA_VISIBLE_DEVICES=7 \
python -m examples.prompt_agent.step0_eval_local \
  --model-path /mnt/agent-project/ckpts/Alfworld-7B-SFT-hf \
  --game-offset 0 \
  --num-games 30 \
  --max-steps 100 \
  --eval-dataset eval_in_distribution \
  --temperature 0.4 \
  --top-p 1.0 \
  --max-new-tokens 512 \
  --history-length 10 \
  --use-skills-only-memory \
  --skills-json-path /home/nvidia/Jiashu/SkillRL/memory_data/alfworld/claude_style_skills.json \
  --retrieval-mode template \
  --top-k 6 \
  --enable-dynamic-update \
  --update-threshold 0.4 \
  --max-new-skills 3 \
  --save-dir /home/nvidia/Jiashu/SkillRL/eval_results/Alfworld/sft \
  --run-name alfworld_7b_sft_max_100
' > /home/nvidia/Jiashu/SkillRL/logs/nohup_log/step0_eval_local/alf_sft_results_max_100.log 2>&1 &
```

```bash
nohup bash -lc '
cd /home/nvidia/Jiashu/SkillRL
PYTHONPATH=/home/nvidia/Jiashu/SkillRL:${PYTHONPATH:-} \
ALFWORLD_DATA=/home/nvidia/Jiashu/SkillRL/alfworld_data \
CUDA_VISIBLE_DEVICES=0 \
python -m examples.prompt_agent.step0_eval_local \
  --model-path /mnt/agent-project/ckpts/Alfworld-7B-SFT-hf \
  --game-offset 50 \
  --num-games 50 \
  --max-steps 100 \
  --eval-dataset eval_in_distribution \
  --temperature 0.4 \
  --top-p 1.0 \
  --max-new-tokens 512 \
  --history-length 10 \
  --use-skills-only-memory \
  --skills-json-path /home/nvidia/Jiashu/SkillRL/memory_data/alfworld/claude_style_skills.json \
  --retrieval-mode template \
  --top-k 6 \
  --enable-dynamic-update \
  --update-threshold 0.4 \
  --max-new-skills 3 \
  --save-dir /home/nvidia/Jiashu/SkillRL/eval_results/Alfworld/sft \
  --run-name alfworld_7b_sft_50_100
' > /home/nvidia/Jiashu/SkillRL/logs/nohup_log/step0_eval_local/alf_sft_results_50_100.log 2>&1 &
```

```bash
nohup bash -lc '
cd /home/nvidia/Jiashu/SkillRL
PYTHONPATH=/home/nvidia/Jiashu/SkillRL:${PYTHONPATH:-} \
ALFWORLD_DATA=/home/nvidia/Jiashu/SkillRL/alfworld_data \
CUDA_VISIBLE_DEVICES=0 \
python -u -m examples.prompt_agent.step0_eval_local \
  --model-path /mnt/agent-project/ckpts/Alfworld-7B-RL-hf \
  --game-offset 0 \
  --num-games 100 \
  --max-steps 50 \
  --eval-dataset eval_in_distribution \
  --temperature 0.4 \
  --top-p 1.0 \
  --max-new-tokens 512 \
  --history-length 10 \
  --use-skills-only-memory \
  --skills-json-path /home/nvidia/Jiashu/SkillRL/memory_data/alfworld/claude_style_skills.json \
  --retrieval-mode template \
  --top-k 6 \
  --enable-dynamic-update \
  --update-threshold 0.4 \
  --max-new-skills 3 \
  --save-dir /home/nvidia/Jiashu/SkillRL/eval_results/Alfworld/rl \
  --run-name alfworld_7b_rl_0_100
' > /home/nvidia/Jiashu/SkillRL/logs/nohup_log/step0_eval_local/alf_rl_hf_0_100.log 2>&1 &
```

## 跑完140条
```bash
nohup bash -lc '
cd /home/nvidia/Jiashu/SkillRL
PYTHONPATH=/home/nvidia/Jiashu/SkillRL:${PYTHONPATH:-} \
ALFWORLD_DATA=/home/nvidia/Jiashu/SkillRL/alfworld_data \
CUDA_VISIBLE_DEVICES=7 \
python -u -m examples.prompt_agent.step0_eval_local \
  --model-path /mnt/agent-project/ckpts/Alfworld-7B-RL-hf \
  --game-offset 100 \
  --num-games 40 \
  --max-steps 50 \
  --eval-dataset eval_in_distribution \
  --temperature 0.4 \
  --top-p 1.0 \
  --max-new-tokens 512 \
  --history-length 10 \
  --use-skills-only-memory \
  --skills-json-path /home/nvidia/Jiashu/SkillRL/memory_data/alfworld/claude_style_skills.json \
  --retrieval-mode template \
  --top-k 6 \
  --enable-dynamic-update \
  --update-threshold 0.4 \
  --max-new-skills 3 \
  --save-dir /home/nvidia/Jiashu/SkillRL/eval_results/Alfworld/rl \
  --run-name alfworld_7b_rl_100_140
' > /home/nvidia/Jiashu/SkillRL/logs/nohup_log/step0_eval_local/alf_rl_hf_100_140.log 2>&1 &
```

## baseline跑完140条
```bash
nohup bash -lc '
cd /home/nvidia/Jiashu/SkillRL
PYTHONPATH=/home/nvidia/Jiashu/SkillRL:${PYTHONPATH:-} \
ALFWORLD_DATA=/home/nvidia/Jiashu/SkillRL/alfworld_data \
CUDA_VISIBLE_DEVICES=7 \
python -u -m examples.prompt_agent.step0_eval_local \
  --model-path /mnt/agent-project/ckpts/Qwen2.5-7B-Instruct \
  --game-offset 0 \
  --num-games 140 \
  --max-steps 50 \
  --eval-dataset eval_in_distribution \
  --temperature 0.4 \
  --top-p 1.0 \
  --max-new-tokens 512 \
  --history-length 10 \
  --use-skills-only-memory \
  --skills-json-path /home/nvidia/Jiashu/SkillRL/memory_data/alfworld/claude_style_skills.json \
  --retrieval-mode template \
  --top-k 6 \
  --enable-dynamic-update \
  --update-threshold 0.4 \
  --max-new-skills 3 \
  --save-dir /home/nvidia/Jiashu/SkillRL/eval_results/Alfworld/rl \
  --run-name alfworld_qwen_0_140
' > /home/nvidia/Jiashu/SkillRL/logs/nohup_log/step0_eval_local/alf_qwen_0_140.log 2>&1 &
```