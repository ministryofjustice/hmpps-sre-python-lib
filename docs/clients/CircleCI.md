## Classes

### hmpps.CircleCI
Initiates a CircleCI session.


**Example**
```
from hmpps import CircleCI

cc_params = {
  'url': os.getenv(
    'CIRCLECI_API_ENDPOINT',
    'https://circleci.com/api/v1.1/project/gh/ministryofjustice/',
  ),
  'token': os.getenv('CIRCLECI_TOKEN'),
}

cc=CircleCI(cc_params)
```

### Functions

*test_connection*
Tests the connection to CircleCI - returns True if OK

*get_trivy_scan_json_data*
Downloads the latest Trivy scan from CircleCI

*get_circleci_orb_version*
Extracts the version of hmpps-circlec-orb from a dictionary representing the CircleCI config


**Migration**
Replace
```
from classes import CircleCI
```

with

```
from hmpps import CircleCI
```
