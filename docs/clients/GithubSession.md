## Classes

## hmpps.GithubSession

This establishes sessions with Github as part of an org. It also includes functions to read and update specific configurations of a Github repository or carry out other custom processes.


**Migration**
Replace
```
from classes import GithubSession
```

with

```
from hmpps import GithubSession
```


### Functions

*auth(self)*
Purpose: Create the PyGitHub Github client and refresh the organization object.
Inputs: none (uses self.token).
Outputs: sets self.session and self.org.
Notes: logs on failure.

*get_access_token(self)*
Purpose: For GitHub App auth — create a JWT and request an installation access token from the GitHub REST API.
Inputs: uses self.private_key, self.app_id, self.app_installation_id.
Outputs: returns an access token (string).
Side-effects/notes: performs network call; raises on non-2xx responses.

*test_connection(self)*
Purpose: Validate the session by checking rate limits and the organisation object.
Inputs: none.
Outputs: returns True on success; raises SystemExit on failure.
Notes: logs rate-limit information.

*get_rate_limit(self)*
Purpose: Return the core rate-limit object from the GitHub API.
Inputs: none.
Outputs: rate_limit.core or None on error.

*get_org_repo(self, repo_name)*
Purpose: Fetch a repository from the configured organisation.
Inputs: repo_name (string)
Outputs: PyGitHub Repository object or None (on error).

*get_file_yaml(self, repo, path)*
Purpose: Read a file in repo and parse it as YAML.
Inputs: repo (PyGitHub repo), path (string)
Outputs: parsed YAML (dict/list) or None on error/404.
Notes: replaces tabs with two spaces before parsing.

*get_file_json(self, repo, path)*
Purpose: Read and parse a JSON file from a repo.
Inputs: same as above.
Outputs: parsed JSON object or None on error/404.

*get_file_plain(self, repo, path)*
Purpose: Read a file and return plaintext contents.
Inputs: same as above.
Outputs: string contents or None on error/404.

*get_actions(self, repo)*
Purpose: Walk the repository .github directory, find workflow .yml files, and collect non-whitelisted uses entries from them.
Inputs: repo (PyGitHub repo)
Outputs: list of dicts: {'filename': <path>, 'actions': [<action refs>]} (empty list on errors).
Notes: checks only .yml extension (not .yaml).

*api_get(self, api)*
Purpose: Simple wrapper to GET https://api.github.com/{api} and return JSON.
Inputs: api string (path after api.github.com/)
Outputs: parsed JSON dict or empty {} on error.
Notes: always calls get_access_token() to fetch a token string for the header.

*get_codescanning_summary(self, repo)*
Purpose: Aggregate code-scanning alerts into a summary grouped by CVE (highest severity per CVE) and counts per severity.
Inputs: repo (PyGitHub repo)
Outputs: dict { 'counts': {<severity>: n}, 'vulnerabilities': {cve: {severity, url}, ...} } or {} if none.
Notes: treats missing severity as UNKNOWN and sorts vulnerabilities by severity.

*create_update_pr(self, request)*
Purpose: Create/update a JSON request file (under requests/) on a branch named REQ_<id>_<repo> in the bootstrap repo and open or update a PR into main.
Inputs: request dict (must include id, github_repo and optional other fields).
Outputs: returns the modified request dict with PR metadata (e.g., request_github_pr_number, request_github_pr_status, output_status).
Side-effects/notes: Creates branch/ref, writes or updates file, makes PR; may call sys.exit(1) on failures.

*delete_old_workflows(self)*
Purpose: Trim workflow runs for the bootstrap workflow, keeping the most recent 12 runs.
Inputs: none (uses self.bootstrap_repo).
Outputs: None (side effects only).
Notes: Silence/logs GitHub exceptions.

*create_repo(self, project_params)*
Purpose: Create a new repository from a template (preferred) or create a fresh repo in an org; optionally seed a README for the fresh repo flow.
Inputs: project_params dict (keys: github_template_repo, github_org, github_repo, description).
Outputs: None (creates remote resources).
Side-effects/notes: Uses REST endpoint to generate from template or create org repo; polls to wait for repo readiness; may sys.exit(1) on failure.

*add_repo_to_runner_group(self, repo_name, runner_group_name)*
Purpose: Add a repository to an organisation Actions runner group.
Inputs: repo_name, runner_group_name
Outputs: True on success, False on failure.
Notes / caveats: Current implementation references self.github_org (not set) and mixes self.org (object) into REST URLs — likely to raise AttributeError or build incorrect URLs. Also expects GithubException for requests calls (should handle requests exceptions or check response status).