"""Public API for the hmpps library.

Symbols are imported lazily (PEP 562) so that importing ``hmpps`` does not
eagerly pull in heavy optional dependencies (PyGithub, office365, slack_sdk,
flask, etc.). Each symbol is only imported when first accessed.
"""

import importlib
from typing import TYPE_CHECKING

# Maps public name -> submodule providing it (relative to this package).
_LAZY_IMPORTS = {
  'GithubSession': '.clients.github',
  'ServiceCatalogue': '.clients.service_catalogue',
  'CircleCI': '.clients.circleci',
  'Slack': '.clients.slack',
  'SharePoint': '.clients.sharepoint',
  'RepositoryInfoFactory': '.models.repository_info',
  'BasicRepositoryInfo': '.models.repository_info',
  'RepositoryInfo': '.models.repository_info',
  'BranchProtectionInfo': '.models.repository_info',
  'AlertmanagerData': '.models.alertmanager',
  'job_log_handling': '.services.job_log_handling',
  'HealthServer': '.services.health_server',
  'update_dict': '.utils.utilities',
  'fetch_yaml_values_for_key': '.utils.utilities',
  'find_matching_keys': '.utils.utilities',
}

__all__ = list(_LAZY_IMPORTS)


def __getattr__(name: str):
  try:
    module_path = _LAZY_IMPORTS[name]
  except KeyError:
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}') from None
  module = importlib.import_module(module_path, __name__)
  # ``job_log_handling`` is re-exported as the module itself.
  attr = module if name == 'job_log_handling' else getattr(module, name)
  globals()[name] = attr  # cache so subsequent lookups skip __getattr__
  return attr


def __dir__():
  return sorted(list(globals().keys()) + __all__)


if TYPE_CHECKING:
  # Give type checkers / IDEs the real symbols without eager runtime imports.
  from .clients.github import GithubSession
  from .clients.service_catalogue import ServiceCatalogue
  from .clients.circleci import CircleCI
  from .clients.slack import Slack
  from .clients.sharepoint import SharePoint
  from .models.repository_info import (
    RepositoryInfoFactory,
    BasicRepositoryInfo,
    RepositoryInfo,
    BranchProtectionInfo,
  )
  from .models.alertmanager import AlertmanagerData
  from .services import job_log_handling
  from .services.health_server import HealthServer
  from .utils.utilities import (
    update_dict,
    fetch_yaml_values_for_key,
    find_matching_keys,
  )
