import asyncio
import json
import gzip
import unittest
from unittest.mock import MagicMock, patch

from conditional_reads import ConditionalReadMiddleware
from DAO.mermaDAO import get_mermas_page
from starlette.middleware.gzip import GZipMiddleware


class ConditionalReadsTests(unittest.TestCase):
    async def request(self, app, headers=None, method='GET'):
        messages = []
        async def send(message):
            messages.append(message)
        async def receive():
            return {'type': 'http.request', 'body': b''}
        await app({'type': 'http', 'method': method, 'path': '/mermas/sucursales/1',
                   'headers': headers or []}, receive, send)
        return messages

    def test_etag_reuses_body_without_skipping_handler(self):
        asyncio.run(self.check_etag())

    async def check_etag(self):
        calls = []
        payload = {'estatus': 1, 'total': 12}
        async def endpoint(scope, receive, send):
            calls.append(scope)
            body = json.dumps(payload).encode()
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]})
            await send({'type': 'http.response.body', 'body': body})
        app = ConditionalReadMiddleware(endpoint)
        initial = await self.request(app)
        etag = dict(initial[0]['headers'])[b'etag']
        second = await self.request(app, [(b'if-none-match', etag)])
        self.assertEqual(second[0]['status'], 304)
        self.assertEqual(second[1]['body'], b'')
        self.assertEqual(len(calls), 2)
        self.assertNotIn(b'content-length', dict(second[0]['headers']))
        payload['total'] = 13
        changed = await self.request(app, [(b'if-none-match', etag)])
        self.assertEqual(changed[0]['status'], 200)
        self.assertNotEqual(dict(changed[0]['headers'])[b'etag'], etag)

    def test_does_not_cache_errors_or_writes_and_preserves_large_bodies(self):
        asyncio.run(self.check_errors())

    async def check_errors(self):
        async def endpoint(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'{"estatus":0}'})
        error = await self.request(ConditionalReadMiddleware(endpoint))
        self.assertNotIn(b'etag', dict(error[0]['headers']))
        post = await self.request(ConditionalReadMiddleware(endpoint), method='POST')
        self.assertNotIn(b'etag', dict(post[0]['headers']))
        large = await self.request(ConditionalReadMiddleware(endpoint, max_body_bytes=2))
        self.assertEqual(large[1]['body'], b'{"estatus":0}')

    def test_compression_preserves_etag_and_json(self):
        asyncio.run(self.check_compression())

    async def check_compression(self):
        body = json.dumps({'estatus': 1, 'items': ['product'] * 500}).encode()
        async def endpoint(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'application/json')]})
            await send({'type': 'http.response.body', 'body': body})
        app = GZipMiddleware(ConditionalReadMiddleware(endpoint), minimum_size=1024)
        result = await self.request(app, [(b'accept-encoding', b'gzip')])
        headers = dict(result[0]['headers'])
        self.assertEqual(headers[b'content-encoding'], b'gzip')
        self.assertIn(b'etag', headers)
        self.assertEqual(gzip.decompress(result[1]['body']), body)


class MermaPageTests(unittest.TestCase):
    def test_paging_and_totals_use_filtered_set_not_only_page(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {'totalRegistros': 81, 'mermasHoy': 4, 'mermasMes': 20, 'mermasUltimos30Dias': 22},
            {'totalImporte': 1234.50},
        ]
        cursor.fetchall.return_value = [{'idMaMe': 7}]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        with patch('DAO.mermaDAO.get_conn', return_value=conn):
            rows, summary = get_mermas_page(['1', '2'], '2026-10-01', '2026-10-22', 20, 40)
        self.assertEqual(summary['totalRegistros'], 81)
        self.assertEqual(summary['totalImporte'], 1234.50)
        self.assertEqual(rows, [{'idMaMe': 7}])
        calls = cursor.execute.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertIn('COUNT(*)', calls[0][0][0])
        self.assertIn('d.Cantidad * COALESCE(c.Precio, 0)', calls[1][0][0])
        self.assertIn('LIMIT %s OFFSET %s', calls[2][0][0])
        self.assertEqual(calls[2][0][1], ['1', '2', '2026-10-01', '2026-10-22', 20, 40])
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_closes_connection_on_query_failure(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.execute.side_effect = RuntimeError('DB unavailable')
        with patch('DAO.mermaDAO.get_conn', return_value=conn):
            with self.assertRaises(RuntimeError):
                get_mermas_page(['1'])
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_empty_branches_do_not_query_database(self):
        with patch('DAO.mermaDAO.get_conn') as connect:
            rows, summary = get_mermas_page([])
        self.assertEqual(rows, [])
        self.assertEqual(summary['totalImporte'], 0)
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
