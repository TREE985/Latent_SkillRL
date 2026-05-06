import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate ALFWorld SFT evaluation runs into grouped success and "
            "failure JSON files."
        )
    )
    parser.add_argument(
        "--input-root",
        default="/home/nvidia/Jiashu/SkillRL/eval_results/Alfworld/sft",
        help="Directory containing multiple ALFWorld evaluation run folders.",
    )
    parser.add_argument(
        "--success-output",
        default="/home/nvidia/Jiashu/SkillRL/failure_analysis/alfworld/success_responses_grouped.json",
        help="Output path for grouped successful trajectories.",
    )
    parser.add_argument(
        "--failed-output",
        default="/home/nvidia/Jiashu/SkillRL/failure_analysis/alfworld/failed_responses_grouped.json",
        help="Output path for grouped failed trajectories.",
    )
    return parser.parse_args()


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def extract_tag_content(text: str, tag: str) -> str:
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    lower_text = text.lower()
    start_idx = lower_text.find(start_tag)
    end_idx = lower_text.find(end_tag)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return ""
    content_start = start_idx + len(start_tag)
    return text[content_start:end_idx].strip()


def to_grouped_row(episode: dict) -> dict:
    trajectory = episode.get("trajectory", [])
    return {
        "env_idx": episode.get("env_idx", 0),
        "task": episode.get("task", ""),
        "task_type": episode.get("task_type", ""),
        "gamefile": episode.get("gamefile", ""),
        "won": bool(episode.get("won", False)),
        "num_steps": len(trajectory),
        "steps": [
            {
                "step_idx": step.get("step_idx", 0),
                "response": step.get("raw_response", ""),
                "think": extract_tag_content(step.get("raw_response", ""), "think"),
                "action": extract_tag_content(step.get("raw_response", ""), "action"),
            }
            for step in trajectory
        ],
    }


def episode_key(episode: dict) -> str:
    if "dataset_idx" in episode:
        return f"dataset_idx:{episode['dataset_idx']}"
    if episode.get("gamefile"):
        return f"gamefile:{episode['gamefile']}"
    return f"env_idx:{episode.get('env_idx', 0)}"


def collect_latest_episodes(input_root: Path):
    latest = {}
    run_dirs = sorted(
        path for path in input_root.iterdir() if path.is_dir() and (path / "episodes.jsonl").exists()
    )
    for run_dir in run_dirs:
        episodes_path = run_dir / "episodes.jsonl"
        for episode in load_jsonl(episodes_path):
            key = episode_key(episode)
            latest[key] = (run_dir.name, episode)
    return latest


def write_pretty_json(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def main():
    args = parse_args()
    input_root = Path(args.input_root).resolve()
    success_output = Path(args.success_output).resolve()
    failed_output = Path(args.failed_output).resolve()

    latest = collect_latest_episodes(input_root)
    grouped_rows = []
    for run_name, episode in latest.values():
        row = to_grouped_row(episode)
        row["_run_name"] = run_name
        row["_dataset_idx"] = episode.get("dataset_idx")
        grouped_rows.append(row)

    grouped_rows.sort(
        key=lambda row: (
            row["_dataset_idx"] is None,
            row["_dataset_idx"] if row["_dataset_idx"] is not None else row["gamefile"],
        )
    )

    success_rows = []
    failed_rows = []
    for row in grouped_rows:
        clean_row = {
            "env_idx": row["env_idx"],
            "task": row["task"],
            "task_type": row["task_type"],
            "gamefile": row["gamefile"],
            "won": row["won"],
            "num_steps": row["num_steps"],
            "steps": row["steps"],
        }
        if row["won"]:
            success_rows.append(clean_row)
        else:
            failed_rows.append(clean_row)

    write_pretty_json(success_output, success_rows)
    write_pretty_json(failed_output, failed_rows)

    print(f"input_root={input_root}")
    print(f"unique_episodes={len(grouped_rows)}")
    print(f"success_tasks={len(success_rows)}")
    print(f"failed_tasks={len(failed_rows)}")
    print(f"success_output={success_output}")
    print(f"failed_output={failed_output}")


if __name__ == "__main__":
    main()
