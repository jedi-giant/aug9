from openai import OpenAI
from dotenv import load_dotenv
import os


load_dotenv()


def build_client() -> OpenAI:
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "12"))
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "0"))
    if timeout <= 0:
        raise ValueError("OPENAI_TIMEOUT_SECONDS must be positive")
    if max_retries < 0:
        raise ValueError("OPENAI_MAX_RETRIES must not be negative")
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=timeout,
        max_retries=max_retries,
    )


client = build_client()
