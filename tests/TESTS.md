## Tests

### SharePoint

#### Run the test

<pre>
uv run pytest tests/clients/test_sharepoint.py -v -s
</pre>

#### Check for coverage

<pre>
uv run pytest tests/clients/test_sharepoint.py -v -s --cov=hmpps.clients.sharepoint --cov-report=term-missing
</pre>
