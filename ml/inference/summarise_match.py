"""Write a short match summary from a video-analysis run, using an LLM on Bedrock.

The LLM never sees the video. It only describes statistics produced by our own
detector, which keeps the output grounded and auditable:

1. Read the video run's stats from MLflow (summary + per-frame data)
2. Condense them into a compact digest (counts, ball visibility windows, pitch zones)
3. Ask the model for a brief summary under strict instructions (soccer, stats only,
   no invented events, state the data's limitations)
4. Log the summary, the exact prompt, token usage and a trace back to the same run

Environment: MLFLOW_TRACKING_URI, AWS credentials (Pod Identity), BEDROCK_MODEL_ID.
"""
import argparse
import json
import os
import time

import boto3
import mlflow

SYSTEM_PROMPT = """You are an assistant to a football (soccer) analyst. "Football" always means \
association football (soccer), never American football.

You will receive statistics produced by an automated computer-vision detector that ran on a \
short video clip. Write a brief summary (about 120 words) of what the statistics suggest.

Rules:
- Use ONLY the statistics provided. Do not invent goals, passes, shots, tactics, team names, \
player names or scores.
- Describe what can reasonably be inferred: how many people were visible, where and when the \
ball was seen, how play moved across the pitch.
- End with one sentence on the data's limitations, using the data-quality notes provided.
- Plain English, no headings, no bullet points."""

PROMPT_VERSION = "v1"  # bump when SYSTEM_PROMPT changes, so runs record which prompt they used


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", default=None, help="MLflow run ID of the video analysis")
    p.add_argument("--run-id-file", default=None, help="Read the run ID from this file instead")
    p.add_argument("--model-id", default=os.environ.get("BEDROCK_MODEL_ID",
                                                        "us.anthropic.claude-haiku-4-5-20251001-v1:0"))
    p.add_argument("--max-tokens", type=int, default=400)
    p.add_argument("--temperature", type=float, default=0.3)
    return p.parse_args()


def zone(x: float, y: float, width: int, height: int) -> str:
    """Describe a position in broad terms: left/centre/right third, near/far half."""
    across = "left" if x < width / 3 else "right" if x > 2 * width / 3 else "centre"
    depth = "far side" if y < height / 2 else "near side"
    return f"{across}, {depth}"


def build_digest(summary: dict, frames: list[dict], model_info: dict) -> dict:
    width, height = summary.get("frame_width"), summary.get("frame_height")

    # Ball visibility windows: consecutive sampled frames with the ball seen
    windows, start, last = [], None, None
    for f in frames:
        if f["ball_centre"] is not None:
            start = f["time_s"] if start is None else start
            last = f["time_s"]
        elif start is not None:
            windows.append([start, last])
            start = None
    if start is not None:
        windows.append([start, last])

    ball_zones = []
    if width and height:
        for f in frames:
            if f["ball_centre"]:
                z = zone(*f["ball_centre"], width, height)
                if not ball_zones or ball_zones[-1]["zone"] != z:
                    ball_zones.append({"time_s": f["time_s"], "zone": z})

    # Player counts in 5-second buckets
    buckets: dict[int, list[int]] = {}
    for f in frames:
        buckets.setdefault(int(f["time_s"] // 5) * 5, []).append(f["counts"].get("player", 0))
    players_over_time = [{"from_s": b, "avg_players": round(sum(v) / len(v), 1)} for b, v in sorted(buckets.items())]

    return {
        "clip_seconds": summary["clip_seconds"],
        "frames_analysed": summary["frames_analysed"],
        "avg_players_per_frame": summary["avg_players"],
        "avg_goalkeepers_per_frame": summary["avg_goalkeepers"],
        "avg_referees_per_frame": summary["avg_referees"],
        "ball_visible_pct_of_frames": summary["ball_visible_pct"],
        "ball_visible_windows_s": windows,
        "ball_zone_changes": ball_zones,
        "players_over_time": players_over_time,
        "data_quality_notes": [
            f"Detector test mAP is {model_info.get('test_map')} overall and {model_info.get('test_map_ball')} for the ball.",
            "The detector was trained on professional broadcast footage; other camera angles reduce accuracy.",
            f"Only every {summary.get('sampled_every', 'Nth')} frame was analysed.",
            "Counts are per frame, so the same person is counted in every frame they appear.",
        ],
    }


@mlflow.trace(span_type="LLM", name="bedrock_converse")
def call_model(client, model_id: str, digest: dict, max_tokens: int, temperature: float) -> dict:
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": json.dumps(digest, indent=2)}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return {
        "text": response["output"]["message"]["content"][0]["text"],
        "input_tokens": response["usage"]["inputTokens"],
        "output_tokens": response["usage"]["outputTokens"],
        "stop_reason": response.get("stopReason"),
    }


def main() -> None:
    args = parse_args()
    run_id = args.run_id or open(args.run_id_file).read().strip()
    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)

    summary = mlflow.artifacts.load_dict(f"{run.info.artifact_uri}/stats/summary.json")
    frames = mlflow.artifacts.load_dict(f"{run.info.artifact_uri}/stats/per_frame.json")["frames"]
    summary["sampled_every"] = run.data.params.get("every")

    model_info = {}
    model_run_id = run.data.tags.get("model_run_id")
    if model_run_id:
        metrics = client.get_run(model_run_id).data.metrics
        model_info = {"test_map": round(metrics.get("test_map", 0), 3),
                      "test_map_ball": round(metrics.get("test_map_ball", 0), 3)}

    digest = build_digest(summary, frames, model_info)
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    started = time.perf_counter()
    with mlflow.start_run(run_id=run_id):
        result = call_model(bedrock, args.model_id, digest, args.max_tokens, args.temperature)
        latency = time.perf_counter() - started
        mlflow.set_tags({"summary_model_id": args.model_id, "summary_prompt_version": PROMPT_VERSION})
        mlflow.log_metrics({"summary_input_tokens": result["input_tokens"],
                            "summary_output_tokens": result["output_tokens"],
                            "summary_latency_s": round(latency, 2)})
        mlflow.log_dict({"system": SYSTEM_PROMPT, "prompt_version": PROMPT_VERSION,
                         "model_id": args.model_id, "digest": digest}, "summary/prompt.json")
        mlflow.log_text(result["text"], "summary/match_summary.md")

    print(f"Model: {args.model_id} | tokens in/out: {result['input_tokens']}/{result['output_tokens']} "
          f"| {latency:.1f}s | stop: {result['stop_reason']}")
    print("\nMATCH SUMMARY\n" + result["text"])


if __name__ == "__main__":
    main()
