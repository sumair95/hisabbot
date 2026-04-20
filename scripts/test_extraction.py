"""
Manual test harness for the extraction prompt.

Usage:
    python scripts/test_extraction.py "Ahmed ko 500 udhaar diya"
    python scripts/test_extraction.py   # runs a built-in suite

Requires ANTHROPIC_API_KEY (or OPENAI_API_KEY) in .env.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm import extract  # noqa: E402


SUITE = [
    "Ahmed ko 500 ka udhaar diya",
    "Bilal bhai se 1200 wapas mile",
    "2 kg cheeni 300 cash",
    "aaj ki total sales kya hai",
    "kaun kaun udhaar par hai",
    "Akbar trader ko 5000 diye",
    "last wala galat tha",
    "salaam",
    "احمد کو پانچ سو ادھار",
    "Ahmed ka balance batao",
]


async def main():
    if len(sys.argv) > 1:
        inputs = [" ".join(sys.argv[1:])]
    else:
        inputs = SUITE

    for text in inputs:
        try:
            result = await extract(text, is_voice=False)
            print(f"\n>>> {text}")
            print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(f"\n>>> {text}\nERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
