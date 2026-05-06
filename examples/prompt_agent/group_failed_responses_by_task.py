import argparse
import json
import os
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(
        description="Group failed raw responses by task/episode for easier error analysis."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to failed_raw_responses.jsonl.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to <input-dir>/failed_responses_grouped.json.",
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


def main():
    args = parse_args()
    input_path = os.path.abspath(args.input)
    output_path = args.output or os.path.join(
        os.path.dirname(input_path), "failed_responses_grouped.json"
    )

    rows = load_jsonl(input_path)
    grouped = defaultdict(list)
    meta = {}

    for row in rows:
        env_idx = row["env_idx"]
        grouped[env_idx].append(row)
        meta[env_idx] = {
            "env_idx": env_idx,
            "task": row.get("task", ""),
            "task_type": row.get("task_type", ""),
            "gamefile": row.get("gamefile", ""),
        }

    output_rows = []
    for env_idx in sorted(grouped):
        steps = sorted(grouped[env_idx], key=lambda item: item["step_idx"])
        output_rows.append(
            {
                **meta[env_idx],
                "num_steps": len(steps),
                "steps": [
                    {
                        "step_idx": step["step_idx"],
                        "prompt": step["prompt"],
                        "response": step["response"],
                        "think": extract_tag_content(step["response"], "think"),
                        "action": extract_tag_content(step["response"], "action"),
                    }
                    for step in steps
                ],
            }
        )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_rows, f, indent=2, ensure_ascii=False)

    print(f"failed_tasks={len(output_rows)}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
