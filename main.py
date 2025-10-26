import anthropic
import subprocess
import json
from typing import Any

# サブプロセス用のコードレビュースクリプト
SUBPROCESS_SCRIPT = '''
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
問題点、改善提案、良い点を指摘してください。
```python
{code}
```
"""
        }]
    )
    
    return response.content[0].text

if __name__ == "__main__":
    # 標準入力からコードを読み込む
    code = sys.stdin.read()
    result = code_review(code)
    print(json.dumps({"review": result}))
'''

# メインプロセス用のツール定義
tools = [
    {
        "name": "run_code_review_subprocess",
        "description": "サブプロセスでClaudeを起動してコードレビューを実行します",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "レビュー対象のコード"
                }
            },
            "required": ["code"]
        }
    }
]

def run_code_review_subprocess(code: str) -> dict[str, Any]:
    """サブプロセスでコードレビューを実行"""
    # サブプロセス用スクリプトを一時ファイルに保存
    with open("subprocess_reviewer.py", "w") as f:
        f.write(SUBPROCESS_SCRIPT)
    
    # サブプロセスを起動
    process = subprocess.Popen(
        ["python", "subprocess_reviewer.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # コードを渡して実行
    stdout, stderr = process.communicate(input=code)
    
    if process.returncode != 0:
        return {"error": f"サブプロセスでエラーが発生: {stderr}"}
    
    try:
        result = json.loads(stdout)
        return result
    except json.JSONDecodeError:
        return {"error": "サブプロセスの出力が不正です"}

def process_tool_call(tool_name: str, tool_input: dict[str, Any]) -> str:
    """ツール呼び出しを処理"""
    if tool_name == "run_code_review_subprocess":
        result = run_code_review_subprocess(tool_input["code"])
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"error": "Unknown tool"})

def main():
    client = anthropic.Anthropic()
    
    # 初回メッセージ
    messages = [{
        "role": "user",
        "content": "次のPythonコードをサブプロセスのClaudeにレビューしてもらってください:\n\n```python\ndef calculate(x, y):\n    result = x + y\n    return result\n```"
    }]
    
    print("=== メインプロセスClaudeを起動 ===\n")
    
    # エージェントループ
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )
        
        print(f"Stop Reason: {response.stop_reason}")
        
        # 応答を表示
        for block in response.content:
            if hasattr(block, "text"):
                print(f"\nClaude: {block.text}")
        
        # ツール呼び出しがあれば処理
        if response.stop_reason == "tool_use":
            # アシスタントの応答を会話履歴に追加
            messages.append({
                "role": "assistant",
                "content": response.content
            })
            
            # ツールを実行
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n=== ツール実行: {block.name} ===")
                    print(f"入力: {json.dumps(block.input, ensure_ascii=False, indent=2)}\n")
                    
                    result = process_tool_call(block.name, block.input)
                    
                    print(f"結果: {result}\n")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            # ツール結果を会話履歴に追加
            messages.append({
                "role": "user",
                "content": tool_results
            })
        else:
            # 終了
            break
    
    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()