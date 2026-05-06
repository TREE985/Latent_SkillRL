import argparse
import json
import os
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract raw responses for failed episodes from step0 evaluation logs."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Directory containing episodes.jsonl and raw_responses.jsonl.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to <run-dir>/failed_raw_responses.jsonl.",
    )
    return parser.parse_args()


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    args = parse_args()
    run_dir = os.path.abspath(args.run_dir)
    episodes_path = os.path.join(run_dir, "episodes.jsonl")
    raw_path = os.path.join(run_dir, "raw_responses.jsonl")
    output_path = args.output or os.path.join(run_dir, "failed_raw_responses.jsonl")

    episodes = load_jsonl(episodes_path)
    raw_rows = load_jsonl(raw_path)

    failed_episodes = {episode["env_idx"]: episode for episode in episodes if not episode["won"]}
    raw_by_env = defaultdict(list)
    for row in raw_rows:
        env_idx = row["env_idx"]
        if env_idx in failed_episodes:
            raw_by_env[env_idx].append(row)

    extracted_rows = []
    for env_idx, episode in sorted(failed_episodes.items()):
        gamefile = episode.get("gamefile", "")
        task = episode.get("task", "")
        task_type = episode.get("task_type", "")
        for row in sorted(raw_by_env.get(env_idx, []), key=lambda item: item["step_idx"]):
            extracted_rows.append(
                {
                    "env_idx": env_idx,
                    "task": task,
                    "task_type": task_type,
                    "gamefile": gamefile,
                    "step_idx": row["step_idx"],
                    "prompt": row["prompt"],
                    "response": row["response"],
                }
            )

    with open(output_path, "w", encoding="utf-8") as f:
        for row in extracted_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"failed_episodes={len(failed_episodes)}")
    print(f"extracted_rows={len(extracted_rows)}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()

# python /home/nvidia/Jiashu/SkillRL/examples/prompt_agent/extract_failed_raw_responses.py \
#   --run-dir /home/nvidia/Jiashu/SkillRL/logs/step0_eval_local/local_skillbank_eval_id_offset0_n20