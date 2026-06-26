from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import yaml
import os
import json
from schema import PromptConfig
import argparse



def load_prompt(version: str) -> PromptConfig:
    path = f"prompts/{version}.yaml"
    if not os.path.exist(path):
        raise FileNotFound("file not found")

    with open(path) as f:
        return PromptConfig.model_validate(yaml.safe_load(f))

def build_system_prompts(prompt: PromptConfig):
    if not prompt.few_shot_examples:
        return prompt.system_prompt
    
    shots = "\n".join(
        f"Email: {ex.input}  " for ex in prompt.few_shot_examples
        )





def run_evaluation(version: str):
    """
        runs an evaluation for prompt against golden test set
    """
    prompts = load_prompts(version)
    ground_truths = load_ground_truth()
    system_prompt = build_system_prompts() 

    llm = HuggingFaceEndpoint(
        repo_id= os.getenv("MODEL"),
        huggingfacehub_api_token=os.getenv("HUGGING_FACE_API_KEY")
    )

    agent = ChatHuggingFace(llm=llm)

    correct = 0
    failure = []

    for item in ground_truths:
        result = agent.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=item["email"]),
        ])

        try:
            parsed = json.loads(result.content)
            predicted = parsed["category"]
        except (json.JSONDecodeError, KeyError):
            predicted = "parse_error"

        expected = item["expected"]
        is_correct = expected == predicted
        if is_correct:
            correct  += 1
        else:
            failure.append({"id": item["id"], "expected": expected, "got": predicted})
        status = "PASS" if expected == predicted else "FAIL"
        print(f"  [{status}] {item['id']:15s}  expected={expected:10s}  got={predicted}")

    total = len(ground_truth)
    accuracy_percent = (correct / ground_truth) * 100

    print(f"Result: {correct}/{total} correct  ({accuracy:.0f}% accuracy)")

if __name__=='main':
    parser = argparse.Argument_Parser(description:"Evaluate a prompt version agaisnt golden test set")
    parser.add_argument("version", help="Prompt version to test, v1 or v2")
    args = parser.parse_args()
    run_evaluation(args.version)
