
import os
from openai import OpenAI
from dotenv import load_dotenv

from src.config import BASE_DIR

load_dotenv(BASE_DIR / ".env")


class LLMClient:

    def __init__(self):
        api_key = os.getenv("DASHSCOPE_API_KEY")

        if not api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY")

        self.model = os.getenv(
            "RAG_LLM_MODEL", "qwen-plus"
        )

        self.client = OpenAI(
            api_key=api_key,
            base_url=os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            timeout=60.0,
            max_retries=2
        )

    def chat(self, system_prompt, user_prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )

        return response.choices[0].message.content or ""
