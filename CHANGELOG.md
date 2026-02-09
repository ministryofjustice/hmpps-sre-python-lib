0.0.2 - first commit

0.1.0   - first proper release
0.1.1   - fix to Service Catalogue delete (expect 2xx response rather than expecting 200)
0.1.2   - automate release tagging
0.1.3   - add extra Service Catalogue functions to archive a repository
0.1.4   - improve reliability of github sessions by running auth on every refresh
0.1.5   - add extra Service Catalogue functions to enable migration of Trivy scans
0.1.6   - add an additional Flask health monitor class (HEAT-962) 
0.1.7   - patch fix for repository info to be more tolerant of branch protection not being present
0.1.8   - Added sharepoint_discovery_products_get in service_catalogue without filter part
0.1.9   - First release for hmpps-sre-python-lib - copied from hmpps-python-lib
0.1.10  - Added Python Ruff formatter
0.1.11  - Added branch name to the GitHub PR request response.
0.1.12  - Fix for malformed service catalogue queries
0.1.13  - Patch for urllib3 to fix to >2.6.0 (vulnerability)
0.1.14  - Fix for one more malformed service catalogue query (product_filter)
0.1.15  - Include a rest token when authenticating to Github using a private key

0.2.0   - Refactored ServiceCatalogue and GithubSession classes to authenticate more consistently