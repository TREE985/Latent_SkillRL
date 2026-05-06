import argparse
import json
from collections import Counter
from pathlib import Path

from openai import OpenAI

try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(iterable=None, **kwargs):
        return iterable


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze ALFWorld-style failed trajectories from failed_responses_grouped.json using the OpenAI API."
    )
    parser.add_argument(
        "--input-json",
        default="/home/nvidia/Jiashu/SkillRL/logs/step0_eval_local/local_skillbank_eval_id_offset0_n20/failed_responses_grouped.json",
    )
    parser.add_argument(
        "--prompt-template",
        default="/home/nvidia/Jiashu/SkillRL/failure_analysis/alfworld_failure_analysis_prompt_template.txt",
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model used for failure analysis.",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/nvidia/Jiashu/SkillRL/failure_analysis/alfworld_failed_responses",
    )
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--start-case-id",
        default=None,
        help="Start failure analysis from this failed-case ID, e.g. case_0010.",
    )
    parser.add_argument(
        "--max-steps-per-case",
        type=int,
        default=50,
        help="Maximum number of trajectory steps to include per case.",
    )
    parser.add_argument(
        "--max-think-chars",
        type=int,
        default=280,
        help="Maximum characters kept for each think field.",
    )
    parser.add_argument(
        "--print-case-index",
        type=int,
        default=None,
        help="If set, print the parsed case at this 0-based index before API analysis.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse cases and write no API outputs. Useful for payload inspection without an API key.",
    )
    return parser.parse_args()


def truncate_text(text, max_chars):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def parse_case_id(case_id):
    if case_id is None:
        return None
    case_id = case_id.strip()
    if not case_id.startswith("case_"):
        raise ValueError(f"Invalid case id: {case_id}. Expected format like case_0010")
    return int(case_id.split("_", 1)[1])


def longest_consecutive_run(actions):
    if not actions:
        return {"action": "", "length": 0}

    best_action = actions[0]
    best_len = 1
    current_action = actions[0]
    current_len = 1

    for action in actions[1:]:
        if action == current_action:
            current_len += 1
        else:
            if current_len > best_len:
                best_action = current_action
                best_len = current_len
            current_action = action
            current_len = 1

    if current_len > best_len:
        best_action = current_action
        best_len = current_len

    return {"action": best_action, "length": best_len}


def summarize_actions(steps):
    actions = [step.get("action", "").strip() for step in steps if step.get("action")]
    counter = Counter(actions)
    top_actions = [
        {"action": action, "count": count}
        for action, count in counter.most_common(8)
    ]
    return {
        "num_unique_actions": len(counter),
        "top_actions": top_actions,
        "longest_consecutive_run": longest_consecutive_run(actions),
    }


def summarize_thinks(steps):
    think_mentions = Counter()
    for step in steps:
        think = (step.get("think") or "").lower()
        for keyword in [
            "placed",
            "holding",
            "second",
            "first",
            "systematic",
            "destination first",
            "cool",
            "fridge",
            "toilet",
        ]:
            if keyword in think:
                think_mentions[keyword] += 1
    return dict(think_mentions)


def build_step_payload(step, max_think_chars):
    return {
        "step_idx": step.get("step_idx"),
        "think": truncate_text(step.get("think", ""), max_think_chars),
        "action": step.get("action", ""),
    }


def slice_steps(steps, max_steps_per_case):
    if len(steps) <= max_steps_per_case:
        return steps
    head = max_steps_per_case // 2
    tail = max_steps_per_case - head
    return steps[:head] + steps[-tail:]


def load_failed_cases(json_path, max_steps_per_case, max_think_chars):
    with open(json_path, "r", encoding="utf-8") as f:
        raw_cases = json.load(f)

    parsed_cases = []
    for idx, case in enumerate(raw_cases, start=1):
        raw_steps = case.get("steps", [])
        steps_for_model = slice_steps(raw_steps, max_steps_per_case)
        step_payload = [build_step_payload(step, max_think_chars) for step in steps_for_model]

        parsed_cases.append(
            {
                "case_id": f"case_{idx:04d}",
                "env_idx": case.get("env_idx"),
                "task": case.get("task", ""),
                "task_type": case.get("task_type", ""),
                "gamefile": case.get("gamefile", ""),
                "won": case.get("won", False),
                "num_steps": case.get("num_steps", len(raw_steps)),
                "trajectory_included_steps": len(step_payload),
                "trajectory_was_truncated": len(raw_steps) > len(step_payload),
                "action_summary": summarize_actions(raw_steps),
                "think_keyword_summary": summarize_thinks(raw_steps),
                "steps": step_payload,
            }
        )

    return parsed_cases


def aggregate_local_stats(cases):
    task_type_counts = Counter(case.get("task_type", "unknown") for case in cases)
    longest_runs = [
        case["action_summary"]["longest_consecutive_run"]["length"]
        for case in cases
    ]
    repeated_cases = sum(1 for run in longest_runs if run >= 3)
    exhausted_budget = sum(
        1 for case in cases if case.get("num_steps") == len(case.get("steps", []))
    )
    return {
        "num_failed_cases": len(cases),
        "task_type_counts": dict(task_type_counts),
        "avg_num_steps": round(
            sum(case.get("num_steps", 0) for case in cases) / max(len(cases), 1), 2
        ),
        "cases_with_repeated_action_run_ge_3": repeated_cases,
        "cases_included_full_budget": exhausted_budget,
    }


def call_openai_json(client, model, prompt_template, failed_cases):
    user_payload = {
        "evaluation_setting": {
            "task": "ALFWorld-style action trajectory failure analysis",
            "log_source": "failed_responses_grouped.json",
            "goal": "case-based failure analysis and root-cause attribution",
        },
        "failed_cases": failed_cases,
    }
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt_template},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
            },
        ],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def merge_batch_analyses(batch_results):
    merged_cases = []
    failure_counter = Counter()
    task_type_patterns = []
    recommendations = []

    for item in batch_results:
        merged_cases.extend(item.get("cases", []))
        summary = item.get("aggregate_summary", {})
        for patt in summary.get("top_failure_patterns", []):
            failure_counter[patt.get("failure_type", "unknown")] += patt.get("count", 1)
        task_type_patterns.extend(summary.get("task_type_patterns", []))
        recommendations.extend(summary.get("actionable_recommendations", []))

    top_patterns = [
        {"failure_type": failure_type, "count": count}
        for failure_type, count in failure_counter.most_common()
    ]

    return {
        "cases": merged_cases,
        "aggregate_summary": {
            "top_failure_patterns": top_patterns,
            "task_type_patterns": task_type_patterns,
            "actionable_recommendations": recommendations,
        },
    }


def render_markdown(final_result, local_stats):
    lines = []
    lines.append("# ALFWorld Failure Analysis")
    lines.append("")
    lines.append("## Parsed Summary")
    lines.append(f"- Failed cases: {local_stats['num_failed_cases']}")
    lines.append(f"- Average steps per case: {local_stats['avg_num_steps']}")
    lines.append(
        f"- Cases with repeated action run >= 3: {local_stats['cases_with_repeated_action_run_ge_3']}"
    )
    lines.append(f"- Cases using full included step budget: {local_stats['cases_included_full_budget']}")
    lines.append("- Task type counts:")
    for task_type, count in sorted(local_stats["task_type_counts"].items()):
        lines.append(f"  - {task_type}: {count}")
    lines.append("")
    lines.append("## Top Failure Patterns")
    for item in final_result["aggregate_summary"].get("top_failure_patterns", []):
        lines.append(f"- {item['failure_type']}: {item['count']}")
    lines.append("")
    lines.append("## Per-Case Analysis")
    for case in final_result.get("cases", []):
        lines.append(f"### {case.get('case_id', 'unknown')} | env_idx={case.get('env_idx', '')}")
        lines.append(f"- Task: {case.get('task', '')}")
        lines.append(f"- Task type: {case.get('task_type', '')}")
        lines.append(f"- Failure stage: {case.get('failure_stage', '')}")
        lines.append(f"- Failure type: {case.get('failure_type', '')}")
        lines.append(f"- Confidence: {case.get('confidence', '')}")
        lines.append(f"- Evidence: {case.get('evidence', '')}")
        lines.append(f"- Explanation: {case.get('short_explanation', '')}")
        lines.append(f"- Cause summary: {case.get('concise_cause_summary', '')}")
        lines.append(f"- Suggested fix: {case.get('suggested_fix', '')}")
        lines.append("")
    lines.append("## Recommendations")
    for item in final_result["aggregate_summary"].get("actionable_recommendations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_outputs(output_dir, final_result, local_stats, progress):
    final_result["local_stats"] = local_stats
    final_result["progress"] = progress

    start_id = progress.get("start_case_id") or "case_0001"
    target_id = progress.get("target_end_case_id") or "end"
    stem = f"alfworld_failure_analysis_{start_id}_to_{target_id}"

    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    progress_path = output_dir / "progress.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=2, ensure_ascii=False)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(final_result, local_stats))

    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    return json_path, md_path, progress_path


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.prompt_template, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    print(f"analysis_model={args.model}")

    cases = load_failed_cases(
        json_path=args.input_json,
        max_steps_per_case=args.max_steps_per_case,
        max_think_chars=args.max_think_chars,
    )
    local_stats = aggregate_local_stats(cases)

    if args.print_case_index is not None:
        idx = args.print_case_index
        if idx < 0 or idx >= len(cases):
            raise IndexError(f"print-case-index {idx} out of range for {len(cases)} parsed cases")
        print(json.dumps(cases[idx], indent=2, ensure_ascii=False))

    if args.dry_run:
        print(f"failed_cases={local_stats['num_failed_cases']}")
        print("dry_run=true")
        return

    start_case_num = parse_case_id(args.start_case_id)
    if start_case_num is not None:
        cases = [case for case in cases if parse_case_id(case["case_id"]) >= start_case_num]

    if args.max_cases is not None:
        cases = cases[: args.max_cases]

    if not cases:
        progress = {
            "analysis_model": args.model,
            "start_case_id": args.start_case_id or "case_0001",
            "target_end_case_id": args.start_case_id or "case_0001",
            "last_completed_case_id": None,
            "next_case_id": None,
            "processed_cases": 0,
            "total_failed_cases_in_run": 0,
        }
        empty_result = {
            "cases": [],
            "aggregate_summary": {
                "top_failure_patterns": [],
                "task_type_patterns": [],
                "actionable_recommendations": [],
            },
        }
        json_path, md_path, progress_path = write_outputs(output_dir, empty_result, local_stats, progress)
        print(f"output_json={json_path}")
        print(f"output_md={md_path}")
        print(f"progress_json={progress_path}")
        return

    client = OpenAI()
    batch_results = []
    target_end_case_id = cases[-1]["case_id"]

    batch_starts = range(0, len(cases), args.batch_size)
    num_batches = (len(cases) + args.batch_size - 1) // args.batch_size
    progress_bar = tqdm(
        batch_starts,
        total=num_batches,
        desc="Analyzing ALFWorld failures",
    )
    for batch_start in progress_bar:
        batch = cases[batch_start : batch_start + args.batch_size]
        result = call_openai_json(
            client=client,
            model=args.model,
            prompt_template=prompt_template,
            failed_cases=batch,
        )
        batch_results.append(result)

        processed_cases = min(batch_start + len(batch), len(cases))
        next_case_id = cases[processed_cases]["case_id"] if processed_cases < len(cases) else None
        progress = {
            "analysis_model": args.model,
            "start_case_id": cases[0]["case_id"],
            "target_end_case_id": target_end_case_id,
            "last_completed_case_id": batch[-1]["case_id"],
            "next_case_id": next_case_id,
            "processed_cases": processed_cases,
            "total_failed_cases_in_run": len(cases),
        }
        partial_result = merge_batch_analyses(batch_results)
        json_path, md_path, progress_path = write_outputs(output_dir, partial_result, local_stats, progress)
        if hasattr(progress_bar, "set_postfix"):
            progress_bar.set_postfix(
                last_case=batch[-1]["case_id"],
                done=processed_cases,
                total=len(cases),
            )

    final_result = merge_batch_analyses(batch_results)
    final_progress = {
        "analysis_model": args.model,
        "start_case_id": cases[0]["case_id"],
        "target_end_case_id": target_end_case_id,
        "last_completed_case_id": cases[-1]["case_id"],
        "next_case_id": None,
        "processed_cases": len(cases),
        "total_failed_cases_in_run": len(cases),
    }
    json_path, md_path, progress_path = write_outputs(output_dir, final_result, local_stats, final_progress)

    print(f"failed_cases={local_stats['num_failed_cases']}")
    print(f"start_case_id={final_progress['start_case_id']}")
    print(f"last_completed_case_id={final_progress['last_completed_case_id']}")
    print(f"next_case_id={final_progress['next_case_id']}")
    print(f"output_json={json_path}")
    print(f"output_md={md_path}")
    print(f"progress_json={progress_path}")


if __name__ == "__main__":
    main()
