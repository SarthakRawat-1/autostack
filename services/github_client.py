import asyncio
import base64
import logging
from typing import Dict, List, Any, Optional
import httpx
from api.config import settings
from models.github_models import Repository, Branch, Commit, PullRequest, FileChange

logger = logging.getLogger(__name__)

class GitHubClientError(Exception):
    pass

class GitHubClient:
    BASE_URL = "https://api.github.com"
    API_VERSION = "2022-11-28"
    
    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        self.auth_token = token or settings.github_token
        self.base_url = self.BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.API_VERSION
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"

        # Use retry transport if available, otherwise use default
        try:
            from httpx_retry import AsyncRetryTransport
            transport = AsyncRetryTransport()  # Use default settings
        except (ImportError, TypeError):
            transport = None  # Fall back to default httpx transport
        
        try:
            client_kwargs = {
                "timeout": self.timeout,
                "headers": self._get_headers()
            }
            if transport:
                client_kwargs["transport"] = transport
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.request(method, url, **kwargs)

                if response.status_code == 401:
                    raise GitHubClientError("Authentication failed. Check GitHub token.")
                elif response.status_code == 404:
                    raise GitHubClientError("Resource not found")
                elif response.status_code == 403 and "rate limit" in response.text.lower():
                    raise GitHubClientError("GitHub API rate limit exceeded")
                elif response.status_code >= 400:
                    raise GitHubClientError(
                        f"GitHub API request failed with status {response.status_code}: {response.text}"
                    )

                if response.status_code == 204:
                    return {}
                
                return response.json()
                
        except httpx.HTTPError as e:
            raise GitHubClientError(f"Request failed: {str(e)}") from e
    
    async def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = True,
        auto_init: bool = True
    ) -> Repository:
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init
        }
        
        logger.info(f"Creating GitHub repository: {name}")
        result = await self._request("POST", "/user/repos", json=data)
        repo = Repository(result)
        logger.info(f"Created repository: {repo.full_name} at {repo.url}")
        return repo
    
    async def create_branch(
        self,
        repo: str,
        branch_name: str,
        from_branch: str = "main"
    ) -> Branch:
        logger.info(f"Creating branch '{branch_name}' from '{from_branch}' in {repo}")
        ref_result = await self._request("GET", f"/repos/{repo}/git/ref/heads/{from_branch}")
        source_sha = ref_result["object"]["sha"]

        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": source_sha
        }
        
        await self._request("POST", f"/repos/{repo}/git/refs", json=data)

        branch_result = await self._request("GET", f"/repos/{repo}/branches/{branch_name}")
        logger.info(f"Created branch: {branch_name}")
        return Branch(branch_result)
    
    async def commit_files(
        self,
        repo: str,
        branch: str,
        files: List[FileChange],
        message: str,
        author_name: str = "AutoStack Bot",
        author_email: str = "autostack@example.com"
    ) -> Commit:
        ref_result = await self._request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        base_sha = ref_result["object"]["sha"]

        commit_result = await self._request("GET", f"/repos/{repo}/git/commits/{base_sha}")
        base_tree_sha = commit_result["tree"]["sha"]

        tree_items = []
        for file in files:
            blob_data = {"content": file.content, "encoding": "utf-8"}
            blob_result = await self._request("POST", f"/repos/{repo}/git/blobs", json=blob_data)
            
            tree_items.append({
                "path": file.path,
                "mode": file.mode,
                "type": "blob",
                "sha": blob_result["sha"]
            })

        tree_data = {"base_tree": base_tree_sha, "tree": tree_items}
        tree_result = await self._request("POST", f"/repos/{repo}/git/trees", json=tree_data)

        commit_data = {
            "message": message,
            "tree": tree_result["sha"],
            "parents": [base_sha],
            "author": {"name": author_name, "email": author_email}
        }
        new_commit_result = await self._request("POST", f"/repos/{repo}/git/commits", json=commit_data)

        ref_update_data = {"sha": new_commit_result["sha"], "force": False}
        await self._request("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", json=ref_update_data)
        
        logger.info(f"Committed {len(files)} files to {repo}/{branch}: {message[:50]}...")
        return Commit(new_commit_result)
    
    async def create_pull_request(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str = ""
    ) -> PullRequest:
        data = {"title": title, "head": head, "base": base, "body": body}
        logger.info(f"Creating PR in {repo}: {head} -> {base}")
        result = await self._request("POST", f"/repos/{repo}/pulls", json=data)
        pr = PullRequest(result)
        logger.info(f"Created PR #{pr.number}: {pr.url}")
        return pr
    
    async def get_file_content(self, repo: str, path: str, ref: str = "main") -> str:
        result = await self._request("GET", f"/repos/{repo}/contents/{path}", params={"ref": ref})
        
        if "content" in result:
            content_b64 = result["content"].replace("\n", "")
            content_bytes = base64.b64decode(content_b64)
            return content_bytes.decode("utf-8")
        else:
            raise GitHubClientError(f"No content found for file: {path}")
    
    async def list_repository_files(self, repo: str, ref: str = "main", path: str = "") -> List[str]:
        result = await self._request("GET", f"/repos/{repo}/contents/{path}", params={"ref": ref})
        
        files = []
        items = result if isinstance(result, list) else [result]
        
        for item in items:
            if item["type"] == "file":
                files.append(item["path"])
            elif item["type"] == "dir":
                subdir_files = await self.list_repository_files(repo=repo, ref=ref, path=item["path"])
                files.extend(subdir_files)
        
        return files
    
    async def get_repository(self, repo: str) -> Repository:
        result = await self._request("GET", f"/repos/{repo}")
        return Repository(result)
    
    async def list_branches(self, repo: str) -> List[Branch]:
        result = await self._request("GET", f"/repos/{repo}/branches")
        return [Branch(branch_data) for branch_data in result]
    
    async def add_pr_comment(self, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        data = {"body": comment}
        return await self._request("POST", f"/repos/{repo}/issues/{pr_number}/comments", json=data)
    
    async def wait_for_checks(
        self,
        repo: str,
        ref: str,
        timeout: int = 300,
        poll_interval: int = 10
    ) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if elapsed > timeout:
                return {
                    "conclusion": "timed_out",
                    "status": "timed_out",
                    "completed": False,
                    "error": f"Timeout after {timeout} seconds"
                }
            
            try:
                result = await self._request("GET", f"/repos/{repo}/commits/{ref}/check-runs")
                check_runs = result.get("check_runs", [])
                
                if not check_runs:
                    await asyncio.sleep(poll_interval)
                    continue
                
                all_completed = all(run.get("status") == "completed" for run in check_runs)
                
                if not all_completed:
                    await asyncio.sleep(poll_interval)
                    continue
                
                conclusions = [run.get("conclusion") for run in check_runs]
                
                if "failure" in conclusions:
                    overall_conclusion = "failure"
                elif "cancelled" in conclusions:
                    overall_conclusion = "cancelled"
                elif "timed_out" in conclusions:
                    overall_conclusion = "timed_out"
                elif "neutral" in conclusions:
                    overall_conclusion = "neutral"
                else:
                    overall_conclusion = "success"
                
                first_run = check_runs[0]
                
                return {
                    "conclusion": overall_conclusion,
                    "status": "completed",
                    "completed": True,
                    "workflow_name": first_run.get("name", "CI"),
                    "html_url": first_run.get("html_url", ""),
                    "check_runs_count": len(check_runs),
                    "details": [
                        {
                            "name": run.get("name"),
                            "conclusion": run.get("conclusion"),
                            "html_url": run.get("html_url")
                        }
                        for run in check_runs
                    ]
                }
                
            except GitHubClientError as e:
                if "not found" in str(e).lower():
                    await asyncio.sleep(poll_interval)
                    continue
                raise
    
    async def get_failed_workflow_run(
        self,
        repo: str,
        ref: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent failed workflow run for a commit.
        
        Args:
            repo: Repository name (owner/repo)
            ref: Git ref (commit SHA)
            
        Returns:
            Workflow run info or None if no failed runs
        """
        try:
            # Get check runs for the commit
            response = await self._request(
                "GET",
                f"/repos/{repo}/commits/{ref}/check-runs"
            )
            
            check_runs = response.get("check_runs", [])
            
            # Find the failed run
            for run in check_runs:
                if run.get("conclusion") == "failure":
                    return {
                        "id": run.get("id"),
                        "name": run.get("name"),
                        "html_url": run.get("html_url"),
                        "details_url": run.get("details_url"),
                        "output": run.get("output", {})
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get workflow run: {e}")
            return None
    
    async def get_workflow_run_logs(
        self,
        repo: str,
        ref: str
    ) -> str:
        """
        Get logs from a failed workflow run.
        
        Args:
            repo: Repository name (owner/repo)
            ref: Git ref (commit SHA)
            
        Returns:
            Formatted log string with failure details
        """
        try:
            # Get check runs for the commit
            response = await self._request(
                "GET",
                f"/repos/{repo}/commits/{ref}/check-runs"
            )
            
            check_runs = response.get("check_runs", [])
            logs = []
            
            for run in check_runs:
                conclusion = run.get("conclusion", "")
                name = run.get("name", "Unknown")
                
                if conclusion == "failure":
                    # Get output from the check run
                    output = run.get("output", {})
                    title = output.get("title", "")
                    summary = output.get("summary", "")
                    text = output.get("text", "")
                    
                    log_entry = f"""
=== FAILED: {name} ===
Title: {title}
Summary: {summary}
Details:
{text if text else 'No detailed output available'}
"""
                    logs.append(log_entry)
                    
                    # Try to get annotations (specific error lines)
                    annotations = output.get("annotations", [])
                    if annotations:
                        logs.append("\nAnnotations:")
                        for ann in annotations[:10]:  # Limit to 10
                            logs.append(f"  - {ann.get('path')}:{ann.get('start_line')}: {ann.get('message')}")
            
            if not logs:
                return "No failure logs found"
            
            return "\n".join(logs)
            
        except Exception as e:
            logger.error(f"Failed to get workflow logs: {e}")
            return f"Error fetching logs: {e}"