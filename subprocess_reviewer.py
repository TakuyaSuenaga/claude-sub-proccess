import anthropic
import sys
import json

def code_review(code: str) -> str:
    client = anthropic.Anthropic()
    
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""以下のコードをレビューしてください。
```python
{code}
```
"""
        }]
    )
    
    return response.content[0].text

if __name__ == "__main__":
    code = sys.stdin.read()
    result = code_review(code)
    print(json.dumps({"review": result}, ensure_ascii=False))