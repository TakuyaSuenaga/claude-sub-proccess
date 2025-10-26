"""
複数のサブプロセスを並列起動して、
異なる観点からコードレビューを実行する実装例
"""
import asyncio
import json
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient


# サブプロセス用スクリプト（異なるレビュー観点）
REVIEWER_TEMPLATES = {
    "security": '''
import asyncio
import sys
import json
from claude_agent_sdk import query

async def main():
    code = sys.stdin.read()
    result = []
    
    prompt = f"""以下のコードをセキュリティの観点からレビューしてください。
脆弱性やセキュリティリスクに焦点を当ててください。

```python
{code}
```
"""
    
    async for message in query(prompt=prompt):
        if hasattr(message, 'content'):
            for content in message.content:
                if hasattr(content, 'text'):
                    result.append(content.text)
    
    print(json.dumps({"aspect": "security", "review": "\\n".join(result)}, ensure_ascii=False))

asyncio.run(main())
''',
    "performance": '''
import asyncio
import sys
import json
from claude_agent_sdk import query

async def main():
    code = sys.stdin.read()
    result = []
    
    prompt = f"""以下のコードをパフォーマンスの観点からレビューしてください。
効率性や最適化の余地に焦点を当ててください。

```python
{code}
```
"""
    
    async for message in query(prompt=prompt):
        if hasattr(message, 'content'):
            for content in message.content:
                if hasattr(content, 'text'):
                    result.append(content.text)
    
    print(json.dumps({"aspect": "performance", "review": "\\n".join(result)}, ensure_ascii=False))

asyncio.run(main())
''',
    "maintainability": '''
import asyncio
import sys
import json
from claude_agent_sdk import query

async def main():
    code = sys.stdin.read()
    result = []
    
    prompt = f"""以下のコードを保守性の観点からレビューしてください。
可読性、命名規則、ドキュメント、テスト容易性に焦点を当ててください。

```python
{code}
```
"""
    
    async for message in query(prompt=prompt):
        if hasattr(message, 'content'):
            for content in message.content:
                if hasattr(content, 'text'):
                    result.append(content.text)
    
    print(json.dumps({"aspect": "maintainability", "review": "\\n".join(result)}, ensure_ascii=False))

asyncio.run(main())
'''
}


async def run_single_review(aspect: str, code: str) -> dict:
    """単一のレビュープロセスを実行"""
    # スクリプトファイルを作成
    script_path = f"reviewer_{aspect}.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(REVIEWER_TEMPLATES[aspect])
    
    # サブプロセスを起動
    process = await asyncio.create_subprocess_exec(
        "python", script_path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # コードを渡して実行
    stdout, stderr = await process.communicate(input=code.encode('utf-8'))
    
    if process.returncode != 0:
        return {
            "aspect": aspect,
            "status": "error",
            "message": stderr.decode('utf-8')
        }
    
    try:
        result = json.loads(stdout.decode('utf-8'))
        result["status"] = "success"
        return result
    except json.JSONDecodeError as e:
        return {
            "aspect": aspect,
            "status": "error",
            "message": f"JSON parse error: {str(e)}"
        }


@tool(
    "run_parallel_code_reviews",
    "複数のサブプロセスを並列起動して、異なる観点からコードレビューを実行します",
    {
        "code": {
            "type": "string",
            "description": "レビュー対象のPythonコード"
        },
        "aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "レビュー観点のリスト (security, performance, maintainability)"
        }
    }
)
async def run_parallel_code_reviews(args):
    """並列コードレビューツール"""
    code = args["code"]
    aspects = args.get("aspects", ["security", "performance", "maintainability"])
    
    print(f"\n🚀 {len(aspects)}個のサブプロセスを並列起動中...\n")
    
    try:
        # すべてのレビューを並列実行
        tasks = [run_single_review(aspect, code) for aspect in aspects]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 結果を整形
        review_text = "## 並列コードレビュー結果\n\n"
        
        for result in results:
            if isinstance(result, Exception):
                review_text += f"❌ **エラー**: {str(result)}\n\n"
                continue
            
            if result["status"] == "error":
                review_text += f"❌ **{result['aspect']}**: エラー - {result['message']}\n\n"
            else:
                review_text += f"### 📋 {result['aspect'].upper()}\n\n"
                review_text += f"{result['review']}\n\n"
                review_text += "---\n\n"
        
        return {
            "content": [{
                "type": "text",
                "text": review_text
            }]
        }
        
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ 並列実行中にエラーが発生: {str(e)}"
            }]
        }


async def main():
    """メインエージェント"""
    
    # MCPサーバーを作成
    mcp_server = create_sdk_mcp_server(
        name="parallel-review-tools",
        version="1.0.0",
        tools=[run_parallel_code_reviews]
    )
    
    # エージェントオプション
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        system_prompt="""あなたは包括的なコードレビューマネージャーです。
ユーザーからコードレビューの依頼があったら、複数の観点から並列でレビューを実行してください。
run_parallel_code_reviews ツールを使用して、security、performance、maintainability の3つの観点から
同時にレビューを行い、統合された結果を報告してください。""",
        mcp_servers={
            "review": mcp_server
        },
        allowed_tools=["mcp__review__run_parallel_code_reviews"]
    )
    
    # レビュー対象のコード
    sample_code = """
import pickle
import os

def load_user_data(filename):
    # ユーザーデータをファイルから読み込む
    with open(filename, 'rb') as f:
        data = pickle.load(f)
    return data

def process_data(data):
    # データ処理（非効率な実装）
    result = []
    for i in range(len(data)):
        for j in range(len(data)):
            if data[i] == data[j] and i != j:
                result.append(data[i])
    return result

# メイン処理
user_file = input("ファイル名を入力: ")
data = load_user_data(user_file)
duplicates = process_data(data)
print(duplicates)
"""
    
    print("=" * 60)
    print("並列コードレビューシステム")
    print("=" * 60)
    print()
    
    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            f"""以下のコードを、security、performance、maintainabilityの
3つの観点から並列にレビューしてください：

```python
{sample_code}
```"""
        )
        
        print("\n📊 レビュー結果:\n")
        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for content in message.content:
                    if hasattr(content, 'text'):
                        print(content.text)


if __name__ == "__main__":
    asyncio.run(main())