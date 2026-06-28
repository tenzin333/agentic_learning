from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import yaml
import os
import json
from schema import PromptConfig
import argparse
from utils import parse_model_json
from metrics import compute_metrics, format_report


load_dotenv()


def load_prompt(version: str) -> PromptConfig:
    path = f"prompts/{version}.yaml"
    if not os.path.exists(path):
        raise FileNotFoundError("file not found")

    with open(path) as f:
        return PromptConfig.model_validate(yaml.safe_load(f))

def build_system_prompts(prompt: PromptConfig):
    if not prompt.few_shot_examples:
        return prompt.system_prompt

    shots = "\n\n".join(
        f"Email: {ex.input}\nOutput: {ex.output}" for ex in prompt.few_shot_examples
    )
    return f"{prompt.system_prompt}\n\nExamples:\n{shots}"

def load_ground_truth():
    path = "tests/ground_truth.yaml"
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found {path}")
    
    with open(path) as f:
        return yaml.safe_load(f)




def run_evaluation(version: str):
    """
        runs an evaluation for prompt against golden test set
    """
    prompts = load_prompt(version)
    ground_truths = load_ground_truth()
    system_prompt = build_system_prompts(prompts) 

    llm = HuggingFaceEndpoint(
        repo_id= os.getenv("MODEL"),
        huggingfacehub_api_token=os.getenv("HUGGING_FACE_API_KEY")
    )

    agent = ChatHuggingFace(llm=llm)

    records = []

    # PHASE 1 — collect: run the model on every email and record what it predicted.
    for item in ground_truths:
        result = agent.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=item["email"]),
        ])

        try:
            cleaned_data = parse_model_json(result.content)
            predicted = cleaned_data["category"]
        except (json.JSONDecodeError, KeyError):
            predicted = "parse_error"

        expected = item["expected_category"]
        records.append({"id": item["id"], "expected": expected, "predicted": predicted})

        status = "PASS" if expected == predicted else "FAIL"
        print(f"  [{status}] {item['id']:15s}  expected={expected:10s}  got={predicted}")

    # PHASE 2 — compute: turn the collected records into metrics, print, and save.
    eval_result = compute_metrics(records, version, os.getenv("MODEL"))
    print(format_report(eval_result))
    path = eval_result.save()
    print(f"\nSaved: {path}")

    return eval_result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Evaluate a prompt version agaisnt golden test set")
    parser.add_argument("version", help="Prompt version to test, v1 or v2")
    args = parser.parse_args()
    run_evaluation(args.version)
