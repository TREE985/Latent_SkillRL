import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from openai import OpenAI

try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(iterable=None, **kwargs):
        return iterable


CASE_START_RE = re.compile(r"^\[([^\]]+)\]\[prompt\]\s?(.*)$")
RESPONSE_RE = re.compile(r"^\[([^\]]+)\]\[response\]\s?(.*)$")
SCORE_RE = re.compile(r"^\[([^\]]+)\]\[score\]\s?([0-9.]+)\s*$")
QUESTION_RE = re.compile(r"Your question:\s*(.+)")
SEARCH_TAG_RE = re.compile(r"<search>(.*?)</search>", re.DOTALL)
ANSWER_TAG_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)
STEP_SEARCH_RE = re.compile(r"Step\s+\d+:<search>(.*?)</search>", re.DOTALL)
STEP_HISTORY_RE = re.compile(
    r"Step\s+(\d+):<search>(.*?)</search>\s*<information>(.*?)</information>",
    re.DOTALL,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze Search evaluation failures from output.log using the OpenAI API."
    )
    parser.add_argument(
        "--log-file",
        default="/home/nvidia/Jiashu/SkillRL/wandb/run-20260406_000005-sxp61jr6/files/output.log",
    )
    parser.add_argument(
        "--prompt-template",
        default="/home/nvidia/Jiashu/SkillRL/examples/search/failure_analysis_prompt_template.txt",
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model used for failure analysis, e.g. gpt-4.1-mini or gpt-4.1.",
    )
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument(
        "--print-case-index",
        type=int,
        default=None,
        help="If set, print the parsed case at this 0-based index before API analysis.",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/nvidia/Jiashu/SkillRL/failure_analysis",
    )
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--start-case-id",
        default=None,
        help="Start failure analysis from this failed-case ID, e.g. case_0010.",
    )
    return parser.parse_args()


def extract_question(prompt_text):
    match = QUESTION_RE.search(prompt_text)
    return match.group(1).strip() if match else ""


def extract_tags(text):
    has_search = "<search>" in text
    has_answer = "<answer>" in text
    if has_answer:
        action_type = "answer"
    elif has_search:
        action_type = "search"
    else:
        action_type = "other"
    return has_search, has_answer, action_type


def extract_searches(text):
    return [item.strip() for item in SEARCH_TAG_RE.findall(text) if item.strip()]


def extract_answer(text):
    answers = [item.strip() for item in ANSWER_TAG_RE.findall(text) if item.strip()]
    return answers[-1] if answers else ""


def extract_history_searches(prompt_text):
    if "History:" not in prompt_text:
        return []
    history_part = prompt_text.split("History:", 1)[1]
    if "Now it's your turn to respond for the current step." in history_part:
        history_part = history_part.split("Now it's your turn to respond for the current step.", 1)[0]
    return [item.strip() for item in STEP_SEARCH_RE.findall(history_part) if item.strip()]


def extract_history_steps(prompt_text):
    if "History:" not in prompt_text:
        return []
    history_part = prompt_text.split("History:", 1)[1]
    if "Now it's your turn to respond for the current step." in history_part:
        history_part = history_part.split("Now it's your turn to respond for the current step.", 1)[0]

    steps = []
    for step_idx, query, information in STEP_HISTORY_RE.findall(history_part):
        steps.append(
            {
                "step_idx": int(step_idx),
                "search_query": query.strip(),
                "search_result": information.strip(),
            }
        )
    return steps


def parse_cases(log_path):
    cases = []
    current = None
    state = None

    with open(log_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")

            case_start = CASE_START_RE.match(line)
            if case_start:
                if current and current.get("score") is not None:
                    cases.append(finalize_case(current))
                benchmark = case_start.group(1)
                current = {
                    "benchmark": benchmark,
                    "prompt_lines": [case_start.group(2)],
                    "response_lines": [],
                    "score": None,
                }
                state = "prompt"
                continue

            if current is None:
                continue

            response_match = RESPONSE_RE.match(line)
            if response_match:
                state = "response"
                current["response_lines"].append(response_match.group(2))
                continue

            score_match = SCORE_RE.match(line)
            if score_match:
                current["score"] = float(score_match.group(2))
                cases.append(finalize_case(current))
                current = None
                state = None
                continue

            if state == "prompt":
                current["prompt_lines"].append(line)
            elif state == "response":
                current["response_lines"].append(line)

    if current and current.get("score") is not None:
        cases.append(finalize_case(current))

    return cases


def finalize_case(case):
    prompt_text = "\n".join(case["prompt_lines"]).strip()
    response_text = "\n".join(case["response_lines"]).strip()
    question = extract_question(prompt_text)
    has_search, has_answer, action_type = extract_tags(response_text)
    history_steps = extract_history_steps(prompt_text)
    history_searches = extract_history_searches(prompt_text)
    response_searches = extract_searches(response_text)
    final_answer = extract_answer(response_text)
    return {
        "question": question,
        "prior_search_steps": history_steps,
        "model_searches": history_searches + response_searches,
        "final_answer": final_answer,
        "score": case["score"],
        "has_search": has_search or bool(history_searches),
        "has_answer": has_answer,
        "action_type": action_type,
    }


def build_failed_case_payload(cases):
    payload = []
    for idx, case in enumerate(cases, start=1):
        payload.append(
            {
                "case_id": f"case_{idx:04d}",
                "question": case["question"],
                "prior_search_steps": case["prior_search_steps"],
                "model_searches": case["model_searches"],
                "final_answer": case["final_answer"],
                "score": case["score"],
            }
        )
    return payload


def parse_case_id(case_id):
    if case_id is None:
        return None
    match = re.fullmatch(r"case_(\d+)", case_id.strip())
    if not match:
        raise ValueError(f"Invalid case id: {case_id}. Expected format like case_0010")
    return int(match.group(1))


def call_openai_json(client, model, prompt_template, failed_cases):
    user_payload = {
        "evaluation_setting": {
            "task": "multi-turn search QA",
            "log_source": "SkillRL Search evaluation output.log",
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


def aggregate_local_stats(cases):
    total = len(cases)
    failed = [c for c in cases if c["score"] == 0.0]
    success = [c for c in cases if c["score"] == 1.0]
    failed_no_answer = sum(1 for c in failed if not c["has_answer"])
    failed_search_only = sum(1 for c in failed if c["has_search"] and not c["has_answer"])
    success_with_answer = sum(1 for c in success if c["has_answer"])
    return {
        "num_cases_parsed": total,
        "num_failed_cases": len(failed),
        "num_success_cases": len(success),
        "failed_without_answer": failed_no_answer,
        "failed_search_only": failed_search_only,
        "success_with_answer": success_with_answer,
    }


def merge_batch_analyses(batch_results):
    merged_cases = []
    pattern_counter = Counter()
    benchmark_patterns = []
    skillbank_hypotheses = []
    recommendations = []

    for item in batch_results:
        merged_cases.extend(item.get("cases", []))
        summary = item.get("aggregate_summary", {})
        for patt in summary.get("top_failure_patterns", []):
            pattern_counter[patt.get("failure_type", "unknown")] += patt.get("count", 1)
        benchmark_patterns.extend(summary.get("benchmark_specific_patterns", []))
        skillbank_hypotheses.extend(summary.get("skillbank_effect_hypotheses", []))
        recommendations.extend(summary.get("actionable_recommendations", []))

    top_patterns = [
        {"failure_type": failure_type, "count": count}
        for failure_type, count in pattern_counter.most_common()
    ]
    return {
        "cases": merged_cases,
        "aggregate_summary": {
            "top_failure_patterns": top_patterns,
            "benchmark_specific_patterns": benchmark_patterns,
            "skillbank_effect_hypotheses": skillbank_hypotheses,
            "actionable_recommendations": recommendations,
        },
    }


def write_outputs(output_dir, final_result, local_stats, progress):
    final_result["local_stats"] = local_stats
    final_result["progress"] = progress

    start_id = progress.get("start_case_id") or "case_0001"
    target_id = progress.get("target_end_case_id") or "end"
    stem = f"failure_analysis_{start_id}_to_{target_id}"

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


def render_markdown(final_result, local_stats):
    lines = []
    lines.append("# Search Failure Analysis")
    lines.append("")
    lines.append("## Parsed Summary")
    lines.append(f"- Parsed cases: {local_stats['num_cases_parsed']}")
    lines.append(f"- Failed cases: {local_stats['num_failed_cases']}")
    lines.append(f"- Success cases: {local_stats['num_success_cases']}")
    lines.append(f"- Failed without final answer: {local_stats['failed_without_answer']}")
    lines.append(f"- Failed search-only: {local_stats['failed_search_only']}")
    lines.append("")
    lines.append("## Top Failure Patterns")
    for item in final_result["aggregate_summary"].get("top_failure_patterns", []):
        lines.append(f"- {item['failure_type']}: {item['count']}")
    lines.append("")
    lines.append("## Per-Case Analysis")
    for case in final_result.get("cases", []):
        lines.append(f"### {case.get('case_id', 'unknown')}")
        lines.append(f"- Question: {case.get('question', '')}")
        lines.append(f"- Failure stage: {case.get('failure_stage', '')}")
        lines.append(f"- Failure type: {case.get('failure_type', '')}")
        lines.append(f"- Confidence: {case.get('confidence', '')}")
        lines.append(f"- Evidence: {case.get('evidence', '')}")
        lines.append(f"- Explanation: {case.get('short_explanation', '')}")
        lines.append(f"- Suggested fix: {case.get('suggested_fix', '')}")
        lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.prompt_template, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    print(f"analysis_model={args.model}")

    cases = parse_cases(args.log_file)

    if args.print_case_index is not None:
        idx = args.print_case_index
        if idx < 0 or idx >= len(cases):
            raise IndexError(f"print-case-index {idx} out of range for {len(cases)} parsed cases")
        print(json.dumps(cases[idx], indent=2, ensure_ascii=False))

    failed_cases = [case for case in cases if case["score"] == 0.0]
    failed_payload = build_failed_case_payload(failed_cases)
    local_stats = aggregate_local_stats(cases)

    start_case_num = parse_case_id(args.start_case_id)
    if start_case_num is not None:
        failed_payload = [item for item in failed_payload if parse_case_id(item["case_id"]) >= start_case_num]

    if args.max_cases is not None:
        failed_payload = failed_payload[: args.max_cases]

    if failed_payload:
        target_end_case_id = failed_payload[-1]["case_id"]
    else:
        target_end_case_id = args.start_case_id or "case_0001"

    client = OpenAI()
    case_results = []
    progress = {
        "analysis_model": args.model,
        "start_case_id": args.start_case_id or "case_0001",
        "target_end_case_id": target_end_case_id,
        "last_completed_case_id": None,
        "next_case_id": failed_payload[0]["case_id"] if failed_payload else None,
        "processed_cases": 0,
        "total_failed_cases_in_run": len(failed_payload),
    }

    output_dir = Path(args.output_dir)
    if args.batch_size != 1:
        print(
            f"batch_size={args.batch_size} requested, but the script saves after each case, "
            "so cases are analyzed one-by-one."
        )

    progress_bar = tqdm(
        enumerate(failed_payload),
        total=len(failed_payload),
        desc="Analyzing search failures",
    )
    for idx, case_payload in progress_bar:
        case_result = call_openai_json(
            client=client,
            model=args.model,
            prompt_template=prompt_template,
            failed_cases=[case_payload],
        )
        case_results.append(case_result)

        processed_up_to = case_payload["case_id"]
        next_idx = idx + 1
        progress = {
            "analysis_model": args.model,
            "start_case_id": args.start_case_id or "case_0001",
            "target_end_case_id": target_end_case_id,
            "last_completed_case_id": processed_up_to,
            "next_case_id": failed_payload[next_idx]["case_id"] if next_idx < len(failed_payload) else None,
            "processed_cases": next_idx,
            "total_failed_cases_in_run": len(failed_payload),
        }

        partial_result = merge_batch_analyses(case_results)
        json_path, md_path, progress_path = write_outputs(output_dir, partial_result, local_stats, progress)
        if hasattr(progress_bar, "set_postfix"):
            progress_bar.set_postfix(
                case_id=processed_up_to,
                done=next_idx,
                total=len(failed_payload),
            )

    final_result = merge_batch_analyses(case_results)
    if not failed_payload:
        progress = {
            "analysis_model": args.model,
            "start_case_id": args.start_case_id or "case_0001",
            "target_end_case_id": target_end_case_id,
            "last_completed_case_id": None,
            "next_case_id": None,
            "processed_cases": 0,
            "total_failed_cases_in_run": 0,
        }
    json_path, md_path, progress_path = write_outputs(output_dir, final_result, local_stats, progress)

    print(f"parsed_cases={local_stats['num_cases_parsed']}")
    print(f"failed_cases={local_stats['num_failed_cases']}")
    print(f"start_case_id={progress['start_case_id']}")
    print(f"last_completed_case_id={progress['last_completed_case_id']}")
    print(f"next_case_id={progress['next_case_id']}")
    print(f"output_json={json_path}")
    print(f"output_md={md_path}")
    print(f"progress_json={progress_path}")


if __name__ == "__main__":
    main()
