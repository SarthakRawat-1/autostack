from typing import Dict, Any


class Repository:
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "")
        self.full_name = data.get("full_name", "")
        self.url = data.get("html_url", "")
        self.default_branch = data.get("default_branch", "main")
        self.private = data.get("private", False)
        self.clone_url = data.get("clone_url", "")
        self.ssh_url = data.get("ssh_url", "")
    
    def __repr__(self) -> str:
        return f"Repository(name={self.name}, url={self.url})"


class Branch: 
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "")
        self.sha = data.get("commit", {}).get("sha", "")
        self.protected = data.get("protected", False)
    
    def __repr__(self) -> str:
        return f"Branch(name={self.name}, sha={self.sha[:7]})"


class Commit:
    def __init__(self, data: Dict[str, Any]):
        self.sha = data.get("sha", "")
        self.message = data.get("commit", {}).get("message", "")
        self.url = data.get("html_url", "")
        self.author = data.get("commit", {}).get("author", {}).get("name", "")
    
    def __repr__(self) -> str:
        return f"Commit(sha={self.sha[:7]}, message={self.message[:50]})"


class PullRequest:
    def __init__(self, data: Dict[str, Any]):
        self.number = data.get("number", 0)
        self.title = data.get("title", "")
        self.url = data.get("html_url", "")
        self.state = data.get("state", "")
        self.head = data.get("head", {}).get("ref", "")
        self.base = data.get("base", {}).get("ref", "")
    
    def __repr__(self) -> str:
        return f"PullRequest(#{self.number}, title={self.title})"


class FileChange:
    def __init__(self, path: str, content: str, mode: str = "100644"):
        self.path = path
        self.content = content
        self.mode = mode
    
    def __repr__(self) -> str:
        return f"FileChange(path={self.path})"
