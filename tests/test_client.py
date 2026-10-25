import unittest
import httpx
from cweb_forge import ForgeClient, AsyncForgeClient, ForgeError

URL = 'https://my-app.forge.cweb.app/v1/'

class ClientTests(unittest.TestCase):
    def test_headers_and_concurrency(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={'id': 'example'})
        with ForgeClient(URL, 'fg_secret', transport=httpx.MockTransport(handler)) as client:
            client.collection('records').create({'a': 1}, idempotency_key='stable')
            client.collection('records').update('00000000-0000-4000-8000-000000000001', {'a': 2}, version=1)
        self.assertEqual(calls[0].headers['Idempotency-Key'], 'stable')
        self.assertEqual(calls[1].headers['If-Match'], '"1"')
        self.assertEqual(calls[0].headers['Authorization'], 'Bearer fg_secret')

    def test_errors_and_redirects(self):
        with ForgeClient(URL, transport=httpx.MockTransport(lambda r: httpx.Response(429, json={'error': {'message': 'Limit', 'code': 'quota_exceeded'}}))) as client:
            with self.assertRaises(ForgeError) as result: client.collection('records').list()
        self.assertEqual(result.exception.code, 'quota_exceeded')
        with self.assertRaises(ValueError): ForgeClient('http://example.org')

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_iteration(self):
        async with AsyncForgeClient(URL, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'items': [{'id': '1'}], 'next_cursor': None}))) as client:
            self.assertEqual([x async for x in client.collection('records').iterate()], [{'id': '1'}])
