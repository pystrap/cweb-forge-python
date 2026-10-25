# cWeb Forge Python SDK

Use Forge from Django, FastAPI, scripts, cWeb Studio and external Python notebooks.
This client requires Python 3.10+. It does not require hosting your app on cWeb.

Documentation: https://cweb.app/docs/forge/
Python guide: https://cweb.app/docs/forge/python
These documentation targets must be published before the public package launch.

```sh
pip install cweb-forge
# Before publication, use: pip install -e ../cweb-forge-python
```

```python
import os
from cweb_forge import ForgeClient

with ForgeClient('https://my-app.forge.cweb.app/v1/',
                 token=os.environ['CWEB_FORGE_KEY']) as forge:
    records = forge.collection('records')
    row = records.create({'name': 'Example'}, idempotency_key='import-job-42-row-1')
    records.update(row['id'], {'name': 'Updated'}, version=row['version'])
    for row in records.iterate(limit=100):
        print(row['id'])
```

For async applications use `AsyncForgeClient`, `async with`, `await` for data
methods and `async for` for iteration. A token callback may supply a fresh
application-user access token; the async client also accepts an async callback.
Never use the cWeb Portal login token as an application token.

Notebook example:

```python
import pandas as pd
# Get a scoped read-only key from your notebook secret store. Do not embed it
# in a shared notebook, output or committed .env file.
with ForgeClient(endpoint, token=secret_from_your_secret_store) as forge:
    sample = forge.collection('sales').list(limit=100)
    frame = pd.DataFrame([row['data'] for row in sample['items']])
```

Use bounded pages for large datasets rather than loading every record into RAM.
`list(field='status', equals='active')` applies a scalar equality filter.
Writes/deletes require the current version. Resolve 409 conflicts by reloading;
do not silently overwrite another writer. Create retries should reuse the same
idempotency key within 24 hours. There are no hidden write retries.

`ForgeError` supplies `status`, `code` and `request_id`. Treat 401 as expired
credentials, 403 as denied access, 429 as a rate/plan limit, and 503 as temporary
unavailability. Keys are scoped and expiring; restrict collections and permissions.
Credentials are never sent across redirects or inherited proxy configuration.

Testing: `pip install -e .`, then `python -m unittest discover -s tests`.
Build: `python -m build`; verify package contents, test on supported Python
versions, then publish a reviewed tag through PyPI trusted publishing.
