```bash
cd /home/nvidia/Jiashu/SkillRL

export CUDA_VISIBLE_DEVICES=0,1,2,3

export MODEL_PATH=/mnt/agent-project/ckpts/Search-7B-RL

export CUDA_VISIBLE_DEVICES=0,1,2,3
export RAY_enable_open_telemetry=0
export MODEL_PATH=/mnt/agent-project/ckpts/Search-7B-SFT-hf

nohup bash -lc '
TRAIN_DATA=/home/nvidia/Jiashu/SkillRL/data/searchR1_processed_direct/test_processed.parquet \
VAL_DATA=/home/nvidia/Jiashu/SkillRL/data/searchR1_processed_direct/test_processed.parquet \
bash examples/grpo_trainer/run_search_skills.sh \
  vllm \
  trainer.val_only=True \
  data.val_batch_size=32
' > /home/nvidia/Jiashu/SkillRL/logs/search/search_eval_sft.log 2>&1 &
```

## failure analysis
### search eval
python /home/nvidia/Jiashu/SkillRL/examples/search/analyze_search_failures_with_api.py \
  --log-file /home/nvidia/Jiashu/SkillRL/wandb/run-20260406_000005-sxp61jr6/files/output.log \
  --print-case-index 0 \
  --max-cases 5

OPENAI_API_KEY="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" \
python /home/nvidia/Jiashu/SkillRL/examples/search/analyze_search_failures_with_api.py \
  --log-file /home/nvidia/Jiashu/SkillRL/wandb/run-20260406_000005-sxp61jr6/files/output.log \
  --prompt-template /home/nvidia/Jiashu/SkillRL/examples/search/failure_analysis_prompt_template.txt \
  --model gpt-4.1-mini \
  --batch-size 2 \
  --output-dir /home/nvidia/Jiashu/SkillRL/failure_analysis \
  --start-case-id case_0070 \
  --max-cases 100

### alfworld
OPENAI_API_KEY="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" \
python /home/nvidia/Jiashu/SkillRL/failure_analysis/analyze_alfworld_failures_with_api.py \
  --input-json /home/nvidia/Jiashu/SkillRL/logs/step0_eval_local/local_skillbank_eval_id_offset0_n20/failed_responses_grouped.json \
  --prompt-template /home/nvidia/Jiashu/SkillRL/failure_analysis/alfworld_failure_analysis_prompt_template.txt \
  --model gpt-4.1-mini \
  --batch-size 2 \
  --output-dir /home/nvidia/Jiashu/SkillRL/failure_analysis \
  --start-case-id case_0001 \
  --max-cases 20

## webshop eval with skills
```bash
cd /home/nvidia/Jiashu/SkillRL

mkdir -p /home/nvidia/Jiashu/SkillRL/logs/webshop

export CUDA_VISIBLE_DEVICES=0,1,2,3
export RAY_enable_open_telemetry=0
export MODEL_PATH=/mnt/agent-project/ckpts/Webshop-7B-SFT-hf

nohup bash -lc '
bash examples/grpo_trainer/run_webshop_skills.sh \
  vllm \
  trainer.val_only=True \
  trainer.total_epochs=0 \
  trainer.val_before_train=True \
  trainer.n_gpus_per_node=4 \
  actor_rollout_ref.rollout.tensor_model_parallel_size=4 \
  +env.skills_only_memory.skills_json_path=/home/nvidia/Jiashu/SkillRL/memory_data/webshop/claude_style_skills.json \
  trainer.default_local_dir=/home/nvidia/Jiashu/SkillRL/logs/webshop/checkpoints/webshop_sft_skills_eval
' > /home/nvidia/Jiashu/SkillRL/logs/webshop/webshop_eval_sft_skills.log 2>&1 &
```
