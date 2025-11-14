## Classes

## hmpps.ServiceCatalogue

This establishes sessions with Github as part of an org. It also includes functions to read and update specific configurations of a Github repository or carry out other custom processes.


*Migration*
Replace
```
from classes import ServiceCatalogue
```

with

```
from hmpps import ServiceCatalogue
```

An additional function has been moved from `processes.scheduled_jobs` into the `ServiceCatalogue` class, since it deals with updating a Service Catalogue reference.

1. Remove
```
import processes.scheduled_jobs as sc_scheduled_job
```

2. Within scripts that call sc_scheduled_job, replace:
```
sc_scheduled_job.update(services, 'STATUS')
```

with
```
sc.update_scheduled_job('STATUS')
```

## Functions

*__init__(self, params)*
Purpose: Build the client: base URL, API key, standard endpoints, headers, and test the connection.
Inputs: params dict, expected keys: url, key, optional filter.
Outputs: sets self.url, self.key, self.api_headers, prebuilt endpoint strings and self.connection_ok (result of test_connection()).

*test_connection(self)*
Purpose: Validate connectivity to the Service Catalogue.
Inputs: none (uses self.url/self.api_headers)
Outputs: True on success, False on failure

*get_with_retry(self, uri: str, max_retries: int = 3, timeout: int = 10) -> List[Any]*
Purpose: Aggregate all pages for a given uri by calling the Service Catalogue v1 endpoint; each page fetched with retry.
Inputs: uri (relative path), optional max_retries, timeout
Outputs: list of data items combined from all pages (data arrays)

*get_all_records(self, table)*
Purpose: Convenience wrapper to get all records for table.
Inputs: table (string)
Outputs: list of records (same as get_with_retry(table))

*get_record(self, table, label, parameter)*
Purpose: Return a single record from table filtered by label == parameter.
Inputs: table (string, may already include query params), label (field name), parameter (value)
Outputs: the first matching record dict, or {} if none found

*update(self, table, element_id, data)*
Purpose: PUT update a record by id
Inputs: table, element_id, data (dict)
Outputs: True on 200 response, False otherwise

*add(self, table, data)*
Purpose: POST (create) a record in table
Inputs: table, data (dict)
Outputs: True on 201, False otherwise

*delete(self, table, element_id)*
Purpose: DELETE a record by id
Inputs: table, element_id
Outputs: True on 200, False otherwise


*get_id(self, match_table, match_field, match_string)*
Purpose: Find the Service Catalogue documentId for a single item matching match_field == match_string.
Inputs: match_table, match_field, match_string
Outputs: documentId string if found, otherwise None

*get_component_env_id(self, component, env)*
Purpose: Return documentId for an environment named env inside a component's envs.
Inputs: component (dict expected to have envs list), env (string)
Outputs: env_id or None

Side-effects: logs whether found or not
Caveat: current implementation contains bugs:
Iterates for env in component.get('envs', {}): reusing the name env (shadowing the parameter).

*find_all_teams_ref_in_sc(self)*
Purpose: Collect combined unique team references from all components' team fields in the Service Catalogue.
Inputs: none
Outputs: set of team identifiers (from github_project_teams_write, github_project_teams_admin, github_project_teams_maintain)


*update_scheduled_job(self, status)*
Purpose: Update the scheduled-jobs entry for the running job with result and timestamps.
Inputs: status (string, e.g. 'Succeeded' or failure marker)
Outputs: True if update succeeded, False on error
