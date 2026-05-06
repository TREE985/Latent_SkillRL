## search eval
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
  --start-case-id case_0020 \
  --max-cases 50


