import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from DAO.mermaDAO import get_productos_catalogo
from main import buscar_productos


class ProductosPaginationTests(unittest.TestCase):
    def test_count_and_page_share_filter(self):
        for filtro in ('leche', None):
            with self.subTest(filtro=filtro):
                conn = MagicMock()
                cursor = conn.cursor.return_value
                cursor.fetchone.return_value = {'total': 135}
                cursor.fetchall.return_value = []
                with patch('DAO.mermaDAO.get_conn', return_value=conn):
                    self.assertEqual(get_productos_catalogo(filtro, 50, 150), ([], 135))
                count, page = cursor.execute.call_args_list
                params = ('%leche%', '%leche%') if filtro else ()
                self.assertEqual(count.args[1], params)
                self.assertEqual(page.args[1], params + (50, 150))
                self.assertIn('COUNT(*)', count.args[0])
                self.assertNotIn('LIMIT', count.args[0])
                self.assertIn('ORDER BY Producto, CodigoBarras LIMIT %s OFFSET %s', page.args[0])
                if filtro:
                    for call in (count, page):
                        self.assertIn('WHERE Producto LIKE %s OR CodigoBarras LIKE %s', call.args[0])
                cursor.close.assert_called_once()
                conn.close.assert_called_once()

    def test_endpoint_contract_and_validation(self):
        app = FastAPI()
        app.get('/productos/buscar')(buscar_productos)
        client = TestClient(app)
        with patch('main.get_productos_catalogo', return_value=([], 135)) as query:
            response = client.get('/productos/buscar?q=leche&limit=50&offset=150')
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual((body['productos'], body['total'], body['limit'], body['offset']),
                             ([], 135, 50, 150))
            query.assert_called_once_with('leche', limit=50, offset=150)
            client.get('/productos/buscar')
            query.assert_called_with(None, limit=50, offset=0)
            query.reset_mock()
            for params in ('limit=0', 'limit=101', 'offset=-1', 'limit=abc'):
                self.assertEqual(client.get('/productos/buscar?' + params).status_code, 422)
            query.assert_not_called()
