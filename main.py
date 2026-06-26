from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import yaml
import os
import json
from schema import PromptConfig


load_dotenv()


def load_prompt(version: str) -> PromptConfig:
    with open(f"prompts/{version}.yaml") as f:
        return PromptConfig.model_validate(yaml.safe_load(f))


prompt = load_prompt("v2")
SYSTEM_PROMPT = prompt.system_prompt

from mails import mails
dummy_mails = mails

llm = HuggingFaceEndpoint(
    repo_id=os.getenv("MODEL"),
    huggingfacehub_api_token=os.getenv("HUGGING_FACE_API_KEY")
)
agent = ChatHuggingFace(llm=llm)

data = []
for mail in dummy_mails:
    result = agent.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=mail)
    ])
    data.append(result.content)


print(data)
        