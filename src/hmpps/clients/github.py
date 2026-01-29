import requests
from base64 import b64decode
import json
import yaml
import jwt
import sys
from time import sleep
from github import Auth, Github
from github import GithubException
from github.GithubException import UnknownObjectException
from datetime import datetime, timedelta, timezone
from hmpps.services.job_log_handling import (
  log_debug,
  log_error,
  log_warning,
  log_info,
  log_critical,
)


class GithubSession:
  def __init__(self, params):
    # Don't progress if there's no private key or access token
    if not params.get('app_private_key') and not params.get('github_access_token'):
      log_error(
        'app_private_key or github_access_token are required to initiate a Github Session'
      )
      sys.exit(1)

    # Sort out the parameters depending on authenticaiton type
    if params.get('app_private_key'):
      self.private_key = b64decode(params.get('app_private_key')).decode('ascii')
      self.app_id = params.get('app_id')
      self.app_installation_id = params['app_installation_id']
    else:
      self.private_key = self.app_id = self.app_installation_id = ''
      self.rest_token = params.get('github_access_token')

    self.org_name = params.get('org', 'ministryofjustice')

    # Create a session with a private key
    self.session = None
    self.auth()
    if self.session:
      try:
        rate_limit = self.session.get_rate_limit()
        self.core_rate_limit = rate_limit.resources.core
        log_info(f'Github API - rate limit: {rate_limit}')
      except Exception as e:
        log_critical(f'Unable to get github rate limit - {e}')
    # Bootstrap repo parameter for bootstrapping
    if github_bootstrap_repo := params.get('github_bootstrap_repo'):
      self.bootstrap_repo = self.org.get_repo(f'{github_bootstrap_repo}')
      log_debug(
        f'Initialised GithubProject with bootstrap repo: {self.bootstrap_repo.name}'
      )
    else:
      self.bootstrap_repo = None

  def auth(self):
    log_debug('Authenticating to Github')
    # if the authentication is with a private key, get a fresh token
    if self.private_key:
      try:
        self.rest_token = self.get_access_token()
      except GithubException as g:
        log_critical(f'Unable to authenticate to the github API - {g}')
        sys.exit(1)
    # Then initiate a session with the token
    self.token = Auth.Token(self.rest_token)
    try:
      self.session = Github(auth=self.token, pool_size=50)
    except GithubException as e:
      log_critical(f'Unable to create a session using the github API - {e}')
      sys.exit(1)

    # Refresh the org object
    try:
      self.org = self.session.get_organization(self.org_name)
    except GithubException as e:
      log_critical(f'Unable to get the Github organisation {self.org_name} - {e}')
      sys.exit(1)

  def get_access_token(self):
    log_debug('Using private key to get access token')
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    payload = {'iat': now, 'exp': now + timedelta(minutes=10), 'iss': self.app_id}
    jwt_token = jwt.encode(payload, self.private_key, algorithm='RS256')
    headers = {
      'Authorization': f'Bearer {jwt_token}',
      'Accept': 'application/vnd.github.v3+json',
    }
    response = requests.post(
      f'https://api.github.com/app/installations/{self.app_installation_id}'
      '/access_tokens',
      headers=headers,
    )
    response.raise_for_status()
    return response.json()['token']

  def test_connection(self):
    # Test auth and connection to github
    try:
      rate_limit = self.session.get_rate_limit()
      self.core_rate_limit = rate_limit.resources.core
      log_info(f'Github API: {rate_limit}')
      # test fetching organisation name
      self.org = self.session.get_organization('ministryofjustice')
      return True
    except Exception as e:
      log_critical('Unable to connect to the github API.')
      raise SystemExit(e) from e
      return None

  def get_rate_limit(self):
    try:
      if self.session:
        return self.session.get_rate_limit().resources.core
    except Exception as e:
      log_error(f'Error getting rate limit: {e}')
      return None

  def get_org_repo(self, repo_name):
    repo = None
    try:
      repo = self.org.get_repo(repo_name)
    except Exception as e:
      log_error(f'Error trying to get the repo {repo_name} from Github: {e}')
      return None
    return repo

  def get_file_yaml(self, repo, path):
    try:
      file_contents = repo.get_contents(path)
      contents = b64decode(file_contents.content).decode().replace('\t', '  ')
      yaml_contents = yaml.safe_load(contents)
      return yaml_contents
    except UnknownObjectException:
      log_debug(f'404 File not found {repo.name}:{path}')
    except Exception as e:
      log_error(f'Error getting yaml file ({path}): {e}')

  def get_file_json(self, repo, path):
    try:
      file_contents = repo.get_contents(path)
      json_contents = json.loads(b64decode(file_contents.content))
      return json_contents
    except UnknownObjectException:
      log_debug(f'404 File not found {repo.name}:{path}')
      return None
    except Exception as e:
      log_error(f'Error getting json file ({path}): {e}')
      return None

  def get_file_plain(self, repo, path):
    try:
      file_contents = repo.get_contents(path)
      plain_contents = b64decode(file_contents.content).decode()
      return plain_contents
    except UnknownObjectException:
      log_debug(f'404 File not found {repo.name}:{path}')
      return None
    except Exception as e:
      log_error(f'Error getting contents from file ({path}): {e}')
      return None

  def api_get(self, api):
    response_json = {}
    log_debug(f'making API call: {api}')
    # GitHub API URL to check security and analysis settings
    url = f'https://api.github.com/{api}'
    token = self.get_access_token()
    log_debug(f'token is: {token}')
    # Headers for the request
    headers = {
      'Authorization': f'token {token}',
      'Accept': 'application/vnd.github.v3+json',
    }
    try:
      # Make the request to check security and analysis settings

      # Check the response status
      response = requests.get(url, headers=headers)
      if response.status_code == 200:
        response_json = response.json()
      else:
        log_error(
          f'Github API GET call failed with response code {response.status_code}'
        )

    except Exception as e:
      log_error(f'Error when making Github API: {e}')
    return response_json

  def get_codescanning_summary(self, repo):
    summary = {}
    alerts = []
    try:
      data = repo.get_codescan_alerts()
      if data:
        for alert in (a for a in data if a.state != 'fixed'):
          # log_debug(
          #   f'\n\nalert is: {json.dumps(alert.raw_data, indent=2)}\n================'
          # )
          # some alerts don't have severity levels
          if alert.rule.security_severity_level:
            severity = alert.rule.security_severity_level.upper()
          else:
            severity = ''
          alert_data = {
            'tool': alert.tool.name,
            'cve': alert.rule.id,
            'severity': severity,
            'url': alert.html_url,
          }
          alerts.append(alert_data)

          log_debug(f'Alert data is:\n{json.dumps(alert_data, indent=2)}')
    except Exception as e:
      log_warning(f'Unable to retrieve codescanning data: {e}')
      # Dictionary to store the best severity per CVE
    vulnerabilities = {}

    log_debug(f'Full alert list:\n{json.dumps(alerts, indent=2)}')
    if alerts:
      # Loop through the alerts
      for alert in alerts:
        cve = alert['cve']
        severity = alert['severity']
        url = alert['url']

        if cve not in vulnerabilities:
          vulnerabilities[cve] = {
            'severity': severity if severity else 'UNKNOWN',
            'url': url,
          }
        else:
          if severity and (
            vulnerabilities[cve]['severity'] == 'UNKNOWN'
            or severity > vulnerabilities[cve]['severity']
          ):
            vulnerabilities[cve] = {'severity': severity, 'url': url}

      log_info(f'vulnerabilities: {json.dumps(vulnerabilities, indent=2)}')

      # Define severity ranking
      severity_order = {'UNKNOWN': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

      # Function to get severity rank
      def get_severity_order(severity):
        return severity_order.get(severity, 0)

      # Sort the CVEs by severity
      sorted_vulnerabilities = {}
      for vulnerability in sorted(
        vulnerabilities.items(),
        key=lambda item: get_severity_order(item[1]['severity']),
        reverse=True,
      ):
        sorted_vulnerabilities[vulnerability[0]] = vulnerability[1]

      # Count severities (adding empty ones to 'UNKNOWN')
      counts = {}
      for vulnerability in vulnerabilities.values():
        if severity := vulnerability.get('severity'):  # Skip empty severities
          counts[severity] = counts.get(severity, 0) + 1
        else:
          counts['UNKNOWN'] = counts.get('UNKNOWN', 0) + 1

      log_info(f'counts: {json.dumps(counts, indent=2)}')

      summary = {
        'counts': counts,
        'vulnerabilities': sorted_vulnerabilities,
      }
    return summary

  def create_update_pr(self, request):
    if request.get('request_type') == 'Archive':
      log_info(f'Request type Archive for repository {request.get("github_repo")}')
      branch_name = f'REQ_ARCHIVE_{request["id"]}_{request.get("github_repo")}'
      json_fields = [
        'request_type',
        'github_org',
        'github_repo',
        'requester_name',
        'requester_email',
        'requester_team',
      ]
    else:
      log_info(f'Request type Add for repository {request.get("github_repo")}')
      branch_name = f'REQ_{request["id"]}_{request.get("github_repo")}'
      json_fields = [
        'request_type',
        'github_repo',
        'repo_description',
        'base_template',
        'jira_project_keys',
        'github_project_visibility',
        'product',
        'github_project_teams_write',
        'github_projects_teams_admin',
        'github_project_branch_protection_restricted_teams',
        'prod_alerts_severity_label',
        'nonprod_alerts_severity_label',
        'slack_channel_nonprod_release_notify',
        'slack_channel_prod_release_notify',
        'slack_channel_security_scans_notify',
        'requester_name',
        'requester_email',
        'requester_team',
      ]

    # If the branch doesn't exist - create it
    # This will obviously create a new PR even if one already exists
    all_branches = self.bootstrap_repo.get_branches()
    if branch_name not in [branch.name for branch in all_branches]:
      log_info(f'Branch {branch_name} not found - creating')
      self.bootstrap_repo.create_git_ref(
        ref=f'refs/heads/{branch_name}',
        sha=self.bootstrap_repo.get_branch('main').commit.sha,
      )

    request_json_file = f'{branch_name}.json'

    # Populate the json file only with useful stuff

    request_json = {key: request.get(key) for key in json_fields if key in request}

    create_file = False
    # Check if the project-request.json file exists and update it if it does
    try:
      json_file = self.bootstrap_repo.get_contents(
        f'requests/{request_json_file}', ref=branch_name
      )
      if json_file and not isinstance(json_file, list):
        self.bootstrap_repo.update_file(
          json_file.path,
          f'Updating {request_json_file} with details for {request.get("github_repo")}',
          json.dumps(request_json, indent=2),
          json_file.sha,
          branch=branch_name,
        )

    except GithubException as e:
      if e.status == 404:
        # Need to create the project.json file if it's not there
        create_file = True
      else:
        log_error(
          f'Failed to update requests/{request_json_file} '
          f'in {self.bootstrap_repo.name} - {e.data} - please fix this this and re-run'
        )
        sys.exit(1)

    if create_file:
      try:
        log_debug(f'Creating file: {request_json_file}')
        self.bootstrap_repo.create_file(
          f'requests/{request_json_file}',
          f'Creating requests/{request_json_file} with details for '
          f'{request.get("github_repo")}',
          json.dumps(request_json, indent=2),
          branch=branch_name,
        )
      except GithubException as e:
        log_error(
          f'Failed to create requests/{request_json_file} in '
          f'{self.bootstrap_repo.name} - {e.data} - please fix this this and re-run'
        )
        sys.exit(1)

    github_pulls = self.bootstrap_repo.get_pulls(
      state='open',
      sort='created',
      base='main',
      head=f'{self.org}:{branch_name}',
    )

    log_debug(f'Current pulls for {branch_name}: {github_pulls.totalCount}')
    if github_pulls.totalCount == 0:
      # Create a new PR if one doesn't exist
      log_info(f'Creating PR for {branch_name}')
      pr = self.bootstrap_repo.create_pull(
        title=f'Project request for {request.get("github_repo")}',
        body=f'Project request raised for {request.get("github_repo")}',
        head=branch_name,
        base='main',
      )
      pr.enable_automerge('MERGE')
      request['request_github_pr_number'] = pr.number
      request['output_status'] = 'New'
      request['request_github_pr_status'] = 'Raised'
    else:
      log_info(f'PR already exists for {branch_name}')
      request['request_github_pr_number'] = github_pulls[0].number
      request['output_status'] = 'Updated'
      request['request_github_pr_status'] = 'Updated'
    request['branch_name'] = branch_name
    return request

  def delete_old_workflows(self):
    try:
      if bootstrap_workflow := [
        workflow
        for workflow in self.bootstrap_repo.get_workflows()
        if workflow.name == 'Bootstrap - poll for repo requests'
      ]:
        workflow_runs = bootstrap_workflow[0].get_runs()
        run_qty = workflow_runs.totalCount
        if run_qty > 12:
          log_debug(
            f'Workflow {bootstrap_workflow[0].name} has {run_qty} runs - cropping to 12'
          )
          for run in workflow_runs[12:]:
            run.delete()

    except GithubException as e:
      log_warning(
        f'Encountered an issue removing old workflow runs in '
        f'{self.bootstrap_repo.name} - {e.data} - please fix this this and re-run'
      )

  def create_repo(self, project_params):
    def _repo_ready():
      # poll for the repo to prevent race conditions
      repo_ready = False
      check_count = 0
      log_debug('Checking to see if the repo is ready yet..')
      while not repo_ready and check_count < 10:
        sleep(5)
        try:
          log_debug(f'Attempt: {check_count}')
          repo.edit(default_branch='main')
          repo_ready = True
        except Exception:
          check_count += 1
          return True

      if not repo_ready:
        log_error(
          f'Repository {project_params["github_repo"]} not ready after 10 attempts - '
          'please check and re-run'
        )
        sys.exit(1)

    if project_params['github_template_repo']:
      # create repository from template
      # Headers for the request
      headers = {
        'Authorization': f'token {self.rest_token}',
        'Accept': 'application/vnd.github.v3+json',
      }

      # Data for the request
      data = {
        'owner': project_params['github_org'],
        'name': project_params['github_repo'],
        'description': project_params['description'],
      }

      # Make the request to create a new repository from a template
      response = requests.post(
        f'https://api.github.com/repos/{project_params["github_org"]}'
        f'/{project_params["github_template_repo"]}/generate',
        headers=headers,
        json=data,
      )

      if response.status_code == 201:
        log_info(f'Repository {project_params["github_repo"]} created successfully.')
      else:
        log_error(
          f'Failed to create repository: {response.status_code} - {response.text}'
        )
        sys.exit(1)

      # Wait for the repo to sync
      _repo_ready()

      # load the repo details into the repo object
      repo = self.session.get_repo(
        f'{project_params["github_org"]}/{project_params["github_repo"]}'
      )

    else:
      # create fresh new repository

      headers = {
        'Authorization': f'token {self.rest_token}',
        'Accept': 'application/vnd.github.v3+json',
      }

      # Data for the request
      data = {
        'name': project_params['github_repo'],
        'description': project_params['description'],
      }

      # Make the request to create a new repository from a template
      response = requests.post(
        f'https://api.github.com/orgs/{project_params["github_org"]}/repos',
        headers=headers,
        json=data,
      )

      if response.status_code == 201:
        log_info(f'Repository {project_params["github_repo"]} created successfully.')
      else:
        log_error(
          f'Failed to create repository: {response.status_code} - {response.text}'
        )
        sys.exit(1)

      # Wait for the repo to sync
      _repo_ready()

      # and populate it with a basic README.md
      repo = self.session.get_repo(
        f'{project_params["github_org"]}/{project_params["github_repo"]}'
      )
      try:
        file_name = 'README.md'
        file_contents = (
          f'# {project_params["github_repo"]}\n{project_params["description"]}'
        )
        repo.create_file(file_name, 'commit', file_contents)
      except GithubException as e:
        log_error(
          'Failed to create Github README.md - '
          f'{e.data} - please correct this and re-run'
        )
        sys.exit(1)

  def archive_repo(self, github_org, github_repo):
    # Archive repository
    # Headers for the request
    headers = {
      'Authorization': f'token {self.rest_token}',
      'Accept': 'application/vnd.github.v3+json',
    }

    # Data for the request
    data = {
      'archived': True,
    }

    # Make the request to create a new repository from a template
    response = requests.post(
      f'https://api.github.com/repos/{github_org}/{github_repo}',
      headers=headers,
      json=data,
    )

    if response.status_code == 200:
      log_info(f'Repository {github_repo} archived successfully.')
    else:
      log_error(
        f'Failed to archive repository: {response.status_code} - {response.text}'
      )
      sys.exit(1)

  def add_repo_to_runner_group(self, repo_name, runner_group_name):
    repo = self.org.get_repo(repo_name)
    if not repo:
      log_error(
        f'Could not find repo {repo_name} - not trying to add it to the runner group'
      )
      return False
    repo_id = repo.id

    headers = {
      'Authorization': f'token {self.rest_token}',
      'Accept': 'application/vnd.github.v3+json',
    }
    try:
      r = requests.get(
        f'https://api.github.com/orgs/{self.org.login}/actions/runner-groups',
        headers=headers,
      )
      r.raise_for_status()
      groups = r.json().get('runner_groups', [])
      if runner_group := next(g for g in groups if g['name'] == runner_group_name):
        runner_group_id = runner_group['id']
      else:
        log_error(
          f'Runner group {runner_group_name} not found -'
          f'not possible to add repository {repo_name} to runner group'
        )
        return False
    except GithubException as e:
      log_error(f'Unable to get a list of runner groups: {e}')
      return False

    try:
      r = requests.put(
        f'https://api.github.com/orgs/{self.org.login}/actions/runner-groups/'
        f'{runner_group_id}/repositories/{repo_id}',
        headers=headers,
      )
      r.raise_for_status()
      log_info(
        f'Repo {repo_name} added to runner group {runner_group_name}'
        f' (id: {runner_group_id}).'
      )
    except GithubException as e:
      log_error(
        f'Unable to add repository {repo_name} to runner group {runner_group_name}: {e}'
      )
      return False

    return True

  def get_teams(self):
    try:
      self.teams = self.org.get_teams()
      self.team_slugs = {team.slug for team in self.teams}
      log_debug(f'Loaded list of {len(self.team_slugs)} team slugs')
      return True
    except Exception as e:
      log_error(f'Unable to load github teams because: {e}')
      return None
