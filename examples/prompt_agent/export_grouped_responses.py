import argparse
import json
import os
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export grouped successful and failed responses from step0 evaluation logs."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Directory containing episodes.jsonl and raw_responses.jsonl.",
    )
    parser.add_argument(
        "--success-output",
        default=None,
        help="Optional success output path. Defaults to <run-dir>/success_responses_grouped.json.",
    )
    parser.add_argument(
        "--failed-output",
        default=None,
        help="Optional failed output path. Defaults to <run-dir>/failed_responses_grouped.json.",
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


def extract_tag_content(text, tag):
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    lower_text = text.lower()
    start_idx = lower_text.find(start_tag)
    end_idx = lower_text.find(end_tag)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return ""
    content_start = start_idx + len(start_tag)
    return text[content_start:end_idx].strip()


def build_grouped_rows(episodes, raw_rows, won_value):
    selected = {episode["env_idx"]: episode for episode in episodes if bool(episode["won"]) == won_value}
    raw_by_env = defaultdict(list)
    for row in raw_rows:
        env_idx = row["env_idx"]
        if env_idx in selected:
            raw_by_env[env_idx].append(row)

    output_rows = []
    for env_idx, episode in sorted(selected.items()):
        steps = sorted(raw_by_env.get(env_idx, []), key=lambda item: item["step_idx"])
        output_rows.append(
            {
                "env_idx": env_idx,
                "task": episode.get("task", ""),
                "task_type": episode.get("task_type", ""),
                "gamefile": episode.get("gamefile", ""),
                "won": bool(episode.get("won", False)),
                "num_steps": len(steps),
                "steps": [
                    {
                        "step_idx": step["step_idx"],
                        "response": step["response"],
                        "think": extract_tag_content(step["response"], "think"),
                        "action": extract_tag_content(step["response"], "action"),
                    }
                    for step in steps
                ],
            }
        )
    return output_rows


def write_pretty_json(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def main():
    args = parse_args()
    run_dir = os.path.abspath(args.run_dir)
    episodes_path = os.path.join(run_dir, "episodes.jsonl")
    raw_path = os.path.join(run_dir, "raw_responses.jsonl")

    success_output = args.success_output or os.path.join(
        run_dir, "success_responses_grouped.json"
    )
    failed_output = args.failed_output or os.path.join(
        run_dir, "failed_responses_grouped.json"
    )

    episodes = load_jsonl(episodes_path)
    raw_rows = load_jsonl(raw_path)

    success_rows = build_grouped_rows(episodes, raw_rows, True)
    failed_rows = build_grouped_rows(episodes, raw_rows, False)

    write_pretty_json(success_output, success_rows)
    write_pretty_json(failed_output, failed_rows)

    print(f"success_tasks={len(success_rows)}")
    print(f"failed_tasks={len(failed_rows)}")
    print(f"success_output={success_output}")
    print(f"failed_output={failed_output}")


if __name__ == "__main__":
    main()
