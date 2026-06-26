from pydantic import BaseModel


class FewShotExample(BaseModel):
    input: str
    output: str


class PromptConfig(BaseModel):
    version: str
    description: str
    system_prompt: str
    few_shot_examples: list[FewShotExample] = []
