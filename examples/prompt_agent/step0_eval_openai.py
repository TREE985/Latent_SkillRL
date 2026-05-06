import argparse
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from omegaconf import OmegaConf
from openai import AzureOpenAI, OpenAI

from agent_system.environments.env_manager import AlfWorldEnvironmentManager
from agent_system.environments.env_package.alfworld import (
    alfworld_projection,
    build_alfworld_envs,
)


TASKS = [
    "pick_and_place",
    "pick_two_obj_and_place",
    "look_at_obj_in_light",
    "pick_heat_then_place_in_recep",
    "pick_cool_then_place_in_recep",
    "pick_clean_then_place_in_recep",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Small-scale step-0 ALFWorld evaluation with OpenAI-compatible APIs."
    )
    parser.add_argument("--provider", choices=["openai", "azure"], default="openai")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--env-num", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--eval-dataset",
        choices=["eval_in_distribution", "eval_out_of_distribution"],
        default="eval_in_distribution",
    )
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-completion-tokens", type=int, default=512)
    parser.add_argument("--history-length", type=int, default=10)
    parser.add_argument(
        "--save-dir",
        default="/home/nvidia/Jiashu/SkillRL/logs/step0_eval_openai",
    )
    parser.add_argument("--run-name", default=None)
    parser.add_argument(
        "--api-base",
        default=None,
        help="Optional base URL for OpenAI-compatible APIs.",
    )
    return parser.parse_args()


def build_config(args):
    return OmegaConf.create(
        {
            "env": {
                "env_name": "alfworld/AlfredTWEnv",
                "seed": args.seed,
                "max_steps": args.max_steps,
                "history_length": args.history_length,
                "use_skills_only_memory": False,
                "use_retrieval_memory": False,
                "alfworld": {
                    "eval_dataset": args.eval_dataset,
                },
            }
        }
    )


def build_env_manager(args):
    alf_config_path = os.path.join(
        os.path.dirname(__file__),
        "../../agent_system/environments/env_package/alfworld/configs/config_tw.yaml",
    )
    env_kwargs = {"eval_dataset": args.eval_dataset}
    resources_per_worker = {"num_cpus": 0.1, "num_gpus": 0.0}

    envs = build_alfworld_envs(
        alf_config_path=alf_config_path,
        seed=args.seed,
        env_num=args.env_num,
        group_n=1,
        resources_per_worker=resources_per_worker,
        is_train=False,
        env_kwargs=env_kwargs,
    )
    return AlfWorldEnvironmentManager(envs, alfworld_projection, build_config(args))


class OpenAIChatAgent:
    def __init__(self, args):
        self.args = args
        self.client = self._build_client()

    def _build_client(self):
        if self.args.provider == "azure":
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            api_version = os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2025-01-01-preview"
            )
            if not endpoint or not api_key:
                raise EnvironmentError(
                    "Azure mode requires AZURE_OPENAI_ENDPOINT and "
                    "AZURE_OPENAI_API_KEY."
                )
            return AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OpenAI mode requires OPENAI_API_KEY.")

        client_kwargs = {"api_key": api_key}
        if self.args.api_base:
            client_kwargs["base_url"] = self.args.api_base
        return OpenAI(**client_kwargs)

    def get_response(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.args.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.args.temperature,
            top_p=self.args.top_p,
            max_completion_tokens=self.args.max_completion_tokens,
        )
        return response.choices[0].message.content.strip()


def extract_task_type(gamefile: str) -> str:
    for task in TASKS:
        if task in gamefile:
            return task
    return "other"


def extract_parsed_action(response_text: str) -> str:
    lower_text = response_text.lower()
    start_tag = "<action>"
    end_tag = "</action>"
    start_idx = lower_text.find(start_tag)
    end_idx = lower_text.find(end_tag)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return ""
    return lower_text[start_idx + len(start_tag) : end_idx].strip()


def make_run_dir(args):
    os.makedirs(args.save_dir, exist_ok=True)
    run_name = args.run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(args.save_dir, run_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def setup_logging(run_dir: str):
    log_fp = os.path.join(run_dir, "run.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[logging.FileHandler(log_fp, encoding="utf-8"), logging.StreamHandler()],
    )


def write_jsonl(path: str, rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    success_by_task = defaultdict(lambda: {"success": 0, "total": 0})
    for item in episodes:
        task_type = item["task_type"]
        success_by_task[task_type]["total"] += 1
        success_by_task[task_type]["success"] += int(item["won"])

    overall = {
        "num_episodes": len(episodes),
        "num_success": sum(int(item["won"]) for item in episodes),
        "success_rate": (
            sum(int(item["won"]) for item in episodes) / len(episodes)
            if episodes
            else 0.0
        ),
        "by_task": {},
    }
    for task_type, stats in success_by_task.items():
        overall["by_task"][task_type] = {
            "success": stats["success"],
            "total": stats["total"],
            "success_rate": stats["success"] / stats["total"],
        }
    return overall


def main():
    args = parse_args()
    run_dir = make_run_dir(args)
    setup_logging(run_dir)

    logging.info("Run directory: %s", run_dir)
    logging.info(
        "Starting step-0 evaluation | provider=%s model=%s env_num=%d max_steps=%d eval_dataset=%s",
        args.provider,
        args.model,
        args.env_num,
        args.max_steps,
        args.eval_dataset,
    )

    agent = OpenAIChatAgent(args)
    env_manager = build_env_manager(args)

    raw_responses_path = os.path.join(run_dir, "raw_responses.jsonl")
    episodes_path = os.path.join(run_dir, "episodes.jsonl")
    summary_path = os.path.join(run_dir, "summary.json")

    raw_rows: List[Dict[str, Any]] = []
    finished_episodes: List[Dict[str, Any]] = []

    try:
        obs, infos = env_manager.reset(kwargs={})
        done_flags = [False] * args.env_num
        episode_traces: List[List[Dict[str, Any]]] = [[] for _ in range(args.env_num)]
        start_time = time.time()

        for step_idx in range(args.max_steps):
            num_done = sum(done_flags)
            logging.info("Step %d | finished %d/%d", step_idx, num_done, args.env_num)

            actions = []
            parsed_actions = [""] * args.env_num
            for env_idx in range(args.env_num):
                if done_flags[env_idx]:
                    actions.append("None")
                    continue

                prompt = obs["text"][env_idx]
                response_text = agent.get_response(prompt)
                actions.append(response_text)
                parsed_actions[env_idx] = extract_parsed_action(response_text)
                raw_rows.append(
                    {
                        "env_idx": env_idx,
                        "step_idx": step_idx,
                        "prompt": prompt,
                        "response": response_text,
                    }
                )

            next_obs, rewards, dones, infos = env_manager.step(actions)

            for env_idx in range(args.env_num):
                if done_flags[env_idx]:
                    continue

                info = infos[env_idx]
                step_record = {
                    "step_idx": step_idx,
                    "prompt": obs["text"][env_idx],
                    "raw_response": actions[env_idx],
                    "parsed_action": parsed_actions[env_idx],
                    "reward": float(rewards[env_idx]),
                    "done": bool(dones[env_idx]),
                    "won": bool(info.get("won", False)),
                    "is_action_valid": bool(info.get("is_action_valid", 0)),
                    "gamefile": info.get("extra.gamefile", ""),
                    "next_observation": next_obs["anchor"][env_idx],
                }
                episode_traces[env_idx].append(step_record)

                if dones[env_idx]:
                    done_flags[env_idx] = True
                    gamefile = info.get("extra.gamefile", "")
                    finished_episodes.append(
                        {
                            "env_idx": env_idx,
                            "task": env_manager.tasks[env_idx],
                            "task_type": extract_task_type(gamefile),
                            "won": bool(info.get("won", False)),
                            "num_steps": len(episode_traces[env_idx]),
                            "gamefile": gamefile,
                            "trajectory": episode_traces[env_idx],
                        }
                    )

            obs = next_obs

            if all(done_flags):
                logging.info("All environments finished early at step %d", step_idx)
                break

        for env_idx in range(args.env_num):
            if done_flags[env_idx]:
                continue
            finished_episodes.append(
                {
                    "env_idx": env_idx,
                    "task": env_manager.tasks[env_idx],
                    "task_type": "unfinished",
                    "won": False,
                    "num_steps": len(episode_traces[env_idx]),
                    "gamefile": "",
                    "trajectory": episode_traces[env_idx],
                }
            )

        summary = summarize(finished_episodes)
        summary["elapsed_seconds"] = time.time() - start_time
        summary["provider"] = args.provider
        summary["model"] = args.model
        summary["eval_dataset"] = args.eval_dataset

        write_jsonl(raw_responses_path, raw_rows)
        write_jsonl(episodes_path, finished_episodes)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logging.info("Finished. Summary saved to %s", summary_path)
        logging.info("Overall success rate: %.4f", summary["success_rate"])
        for task_type, stats in summary["by_task"].items():
            logging.info(
                "%s | %.4f (%d/%d)",
                task_type,
                stats["success_rate"],
                stats["success"],
                stats["total"],
            )

    finally:
        env_manager.close()


if __name__ == "__main__":
    main()
