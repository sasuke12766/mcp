"""
GitHub MCP Server - 优化版
提供 GitHub 仓库管理功能，支持友好的输出格式
"""
import os
import sys
import base64
import json
import subprocess
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# 初始化 MCP Server
mcp = FastMCP("github-mcp")

# GitHub Token（建议通过环境变量设置）
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def print_results(results: dict):
    """美化输出格式，让结果更易读"""
    if "error" in results:
        print(f"❌ 错误: {results['error']}")
        return
    
    if "query" in results:
        print(f"\n🔍 搜索关键词: {results['query']}")
        print(f"📊 找到 {results['total_count']} 个仓库")
        print("-" * 80)
        for i, repo in enumerate(results["results"], 1):
            desc = repo['description']
            short_desc = desc[:50] + '...' if desc and len(desc) > 50 else desc
            print(f"\n{i}. {repo['name']}")
            print(f"   ├─ 作者: {repo['owner']}")
            print(f"   ├─ 描述: {short_desc}")
            print(f"   ├─ ⭐: {repo['stars']}")
            print(f"   ├─ 语言: {repo['language']}")
            print(f"   └─ 链接: {repo['url']}")
    
    elif "username" in results:
        print(f"\n👤 用户: {results['username']}")
        print(f"📦 共有 {results['count']} 个仓库")
        print("-" * 80)
        for i, repo in enumerate(results["repos"], 1):
            desc = repo['description']
            short_desc = desc[:50] + '...' if desc and len(desc) > 50 else desc
            print(f"\n{i}. {repo['name']}")
            print(f"   ├─ 描述: {short_desc}")
            print(f"   ├─ ⭐: {repo['stars']}")
            print(f"   ├─ 语言: {repo['language']}")
            print(f"   ├─ 更新: {repo['updated'][:10]}")
            print(f"   └─ 链接: {repo['url']}")
    
    elif "files" in results:
        print(f"\n📂 {results.get('owner', '')}/{results.get('repo', '')}")
        if "warning" in results:
            print(f"⚠️ {results['warning']}")
        print("-" * 80)
        for f in results["files"]:
            print(f"  {f}")
    
    elif "content" in results:
        print(f"\n📄 {results['name']}")
        print(f"📍 路径: {results['path']}")
        print(f"📏 大小: {results['size']} bytes")
        print("-" * 80)
        print(results["content"])
    
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


@mcp.tool()
def get_user_repos(username: str, sort: str = "updated") -> dict:
    """获取用户的仓库列表"""
    import urllib.request

    url = f"https://api.github.com/users/{username}/repos?sort={sort}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        repos = json.loads(response.read().decode())

    return {
        "username": username,
        "count": len(repos),
        "repos": [
            {
                "name": r["name"],
                "description": r["description"],
                "url": r["html_url"],
                "stars": r["stargazers_count"],
                "language": r["language"],
                "updated": r["updated_at"]
            }
            for r in repos[:20]
        ]
    }


@mcp.tool()
def search_repositories(
    query: str,
    language: Optional[str] = None,
    per_page: int = 10
) -> dict:
    """搜索公开仓库"""
    import urllib.request
    import urllib.parse

    q = query if not language else f"{query} language:{language}"
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&per_page={per_page}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())

    return {
        "query": query,
        "total_count": data["total_count"],
        "results": [
            {
                "name": r["name"],
                "owner": r["owner"]["login"],
                "description": r["description"],
                "url": r["html_url"],
                "stars": r["stargazers_count"],
                "language": r["language"]
            }
            for r in data["items"]
        ]
    }


@mcp.tool()
def download_repo(owner: str, repo: str, dest: str = "./downloads") -> str:
    """下载整个仓库到本地"""
    dest_path = Path(dest) / repo
    url = f"https://github.com/{owner}/{repo}.git"

    cmd = ["git", "clone", "--depth", "1", url, str(dest_path)]
    if GITHUB_TOKEN:
        auth_url = f"https://{GITHUB_TOKEN}@github.com/{owner}/{repo}.git"
        cmd = ["git", "clone", "--depth", "1", auth_url, str(dest_path)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            return f"✅ 成功下载到: {dest_path.absolute()}"
        else:
            return f"❌ 下载失败: {result.stderr[:100]}"
    except subprocess.TimeoutExpired:
        return "⏰ 下载超时，请尝试更小的仓库"
    except Exception as e:
        return f"❌ 下载出错: {str(e)}"


@mcp.tool()
def get_file_content(owner: str, repo: str, path: str, branch: str = "main") -> dict:
    """获取仓库中某个文件的内容"""
    import urllib.request

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        if data.get("encoding") == "base64":
            content = base64.b64decode(data["content"]).decode("utf-8")
            return {
                "name": data["name"],
                "path": data["path"],
                "size": data["size"],
                "content": content,
                "sha": data["sha"]
            }
        else:
            return {"error": "文件非文本格式，无法读取"}
    except urllib.error.HTTPError as e:
        return {"error": f"文件不存在或无权限: {e.code}"}


@mcp.tool()
def get_repo_tree(owner: str, repo: str, branch: str = "main") -> dict:
    """获取仓库的文件目录结构"""
    import urllib.request

    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())

    if data.get("truncated"):
        return {
            "warning": "目录过大，仅显示部分文件",
            "owner": owner,
            "repo": repo,
            "files": [f["path"] for f in data["tree"] if f["type"] == "blob"][:200]
        }

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "files": [f["path"] for f in data["tree"] if f["type"] == "blob"]
    }


if __name__ == "__main__":
    # 如果有命令行参数，执行测试
    if len(sys.argv) > 1:
        if sys.argv[1] == "search":
            query = sys.argv[2] if len(sys.argv) > 2 else "python"
            results = search_repositories(query)
            print_results(results)
        elif sys.argv[1] == "user":
            username = sys.argv[2] if len(sys.argv) > 2 else "octocat"
            results = get_user_repos(username)
            print_results(results)
        elif sys.argv[1] == "tree":
            if len(sys.argv) >= 4:
                results = get_repo_tree(sys.argv[2], sys.argv[3])
                print_results(results)
            else:
                print("用法: python github_mcp.py tree <owner> <repo>")
        elif sys.argv[1] == "file":
            if len(sys.argv) >= 5:
                results = get_file_content(sys.argv[2], sys.argv[3], sys.argv[4])
                print_results(results)
            else:
                print("用法: python github_mcp.py file <owner> <repo> <path>")
        else:
            print("可用命令:")
            print("  search <关键词>    - 搜索仓库")
            print("  user <用户名>      - 获取用户仓库")
            print("  tree <owner> <repo> - 获取目录结构")
            print("  file <owner> <repo> <path> - 获取文件内容")
    else:
        # 启动 MCP 服务器
        mcp.run()