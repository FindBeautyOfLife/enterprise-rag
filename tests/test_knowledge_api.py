"""使用真实 SQLite、文档解析器和 BM25，向量库及大模型边界使用模拟实现。
运行命令：python -m unittest discover -s tests -v
"""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document as WordDocument
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import Settings
from src.services.knowledge_service import KnowledgeService


class FakeStore:
    def __init__(self, name):
        self.name, self.chunks = name, []
        self.client = self

    def sync_document(self, document_id, chunks):
        self.chunks.extend(chunks)

    def count(self):
        return len(self.chunks)

    def delete_collection(self, name):
        pass


class KnowledgeAPITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.temp.name), "unused", "unused", "cpu", 4096)
        self.service = KnowledgeService(self.settings, FakeStore)
        self.client = TestClient(create_app(self.settings, self.service))
        self.client.__enter__()
        self.kb = self.create("制度资料")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def create(self, name):
        response = self.client.post('/api/v1/knowledge-bases', json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def path(self, kb=None):
        return f'/api/v1/knowledge-bases/{kb or self.kb}'

    def upload(self, text="报销申请需要财务审批。\n\n合同签署需要法务审批。", filename="制度.txt", kb=None):
        return self.client.post(self.path(kb) + '/documents', files={"file": (filename, text.encode())})

    def test_crud_persistence_and_cascade(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.client.put(self.path(), json={"name": "财务制度", "description": "测试"}).status_code, 200)
        restarted = KnowledgeService(self.settings, FakeStore)
        self.assertEqual(restarted.list_bases()[0]["document_count"], 1)
        self.assertEqual(restarted.list_bases()[0]["name"], "财务制度")
        self.assertEqual(self.client.delete(self.path()).status_code, 204)
        self.assertEqual(restarted.list_bases(), [])
        with restarted.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0], 0)
        self.assertEqual(self.client.get(self.path() + '/documents').status_code, 404)

    def test_duplicate_and_validation(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.upload(filename="另一个名字.md").status_code, 409)
        self.assertEqual(self.upload(filename="a.exe").status_code, 422)
        self.assertEqual(self.upload(text="").status_code, 422)
        self.assertEqual(self.upload(text="x" * 4097).status_code, 413)
        self.assertEqual(self.upload(filename="broken.docx").status_code, 422)
        self.assertEqual(self.client.post('/api/v1/knowledge-bases', json={"name": " "}).status_code, 422)
        self.assertEqual(self.client.post('/api/v1/knowledge-bases', json={"name": "制度资料"}).status_code, 409)
        self.assertEqual(self.client.post('/api/v1/search', json={"knowledge_base_id": self.kb, "question": " "}).status_code, 422)

    def test_preview_download_replace_and_pagination(self):
        result = self.upload(filename="../../制度.txt").json()
        self.assertEqual(result['filename'], '制度.txt')
        path = self.path() + '/documents/' + result['id']
        preview = self.client.get(path + '/chunks?limit=1').json()
        self.assertEqual(len(preview['items']), 1)
        self.assertGreaterEqual(preview['total'], 2)
        self.assertEqual(self.client.get(path + '/chunks?offset=999').json()['items'], [])
        self.assertEqual(self.client.get(path + '/chunks?limit=0').status_code, 422)
        self.assertIn('财务', self.client.get(path + '/download').content.decode())
        replaced = self.client.put(path, files={'file': ('新版.txt', '新版财务报销流程'.encode())})
        self.assertEqual(replaced.json()['id'], result['id'])
        self.assertEqual(self.client.get(self.path() + '/documents').json()[0]['filename'], '新版.txt')
        self.assertEqual(len(self.client.get(self.path() + '/documents').json()), 1)

    def test_kb_isolation_and_same_filename(self):
        kb2 = self.create('另一个库')
        first = self.upload().json()
        self.assertEqual(self.upload(text='完全不同的资料', kb=kb2).status_code, 201)
        self.assertEqual(self.client.get(self.path(kb2) + '/documents/' + first['id'] + '/download').status_code, 404)
        self.assertEqual(self.client.delete(self.path(kb2) + '/documents/' + first['id']).status_code, 404)
        second = self.upload(text='报销制度补充说明').json()
        parents = [self.client.get(self.path() + '/documents/' + d['id'] + '/chunks').json()['items'][0]['metadata']['parent_id'] for d in [first, second]]
        self.assertNotEqual(*parents)
        result = self.client.post('/api/v1/search', json={'knowledge_base_id': self.kb, 'question': '报销', 'mode': 'keyword', 'top_k': 10})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn('完全不同', str(result.json()))
        self.assertEqual(len(result.json()['items']), 3)

    def test_index_revision_failure_recovery_and_empty(self):
        self.upload()
        result = self.client.post(self.path() + '/reindex')
        self.assertEqual(result.status_code, 200, result.text)
        before = self.service.list_bases()[0]
        self.assertEqual(before['index_status'], 'ready')
        self.assertEqual(result.json()['chunks'], 2)
        self.upload(text='新资料')
        self.assertEqual(self.service.list_bases()[0]['index_status'], 'pending')
        blocked = self.client.post('/api/v1/search', json={'knowledge_base_id': self.kb, 'question': '报销'})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        with patch.object(self.service, '_store', side_effect=RuntimeError('simulated embedding failure')):
            self.assertEqual(self.client.post(self.path() + '/reindex').status_code, 503)
        after = self.service.list_bases()[0]
        self.assertEqual(before['collection'], after['collection'])
        self.assertIsNotNone(after['index_error'])
        self.assertEqual(self.client.post(self.path() + '/reindex').status_code, 200)
        self.assertIsNone(self.service.list_bases()[0]['index_error'])
        for item in self.client.get(self.path() + '/documents').json():
            self.client.delete(self.path() + '/documents/' + item['id'])
        self.assertEqual(self.client.post(self.path() + '/reindex').json()['chunks'], 0)
        self.assertIsNone(self.service.list_bases()[0]['collection'])

    def test_docx_without_charter_and_table(self):
        word = WordDocument()
        word.add_paragraph('普通工作手册，没有第几条的标记。')
        table = word.add_table(rows=1, cols=2)
        table.cell(0, 0).text = '审批人'
        table.cell(0, 1).text = '财务主管'
        raw = io.BytesIO(); word.save(raw)
        from src.loaders.knowledge_loader import parse_upload
        _, _, parents, chunks = parse_upload('手册.docx', raw.getvalue(), 'test-key')
        self.assertTrue(chunks)
        self.assertIn('财务主管', '\n'.join(p.page_content for p in parents))

    def test_legacy_parents_with_prepared_child_ids(self):
        from langchain_core.documents import Document
        from src.vectorstores.id_utils import prepare_chunks
        from src.retrievers.parent_retriever import ParentRetriever
        parent = Document(page_content='原章程内容', metadata={'source': '章程.docx', 'chapter': '第一章', 'article': '第一条'})
        child = prepare_chunks([parent], 'legacy-charter')[0]
        class Retriever:
            def search(self, *args, **kwargs):
                return [{'chunk_id': child.metadata['chunk_id'], 'document': child, 'score': 1.0}]
        result = ParentRetriever(Retriever(), [parent]).search('章程')
        self.assertIs(result[0]['document'], parent)

    def test_ask_uses_selected_pipeline_and_frontend(self):
        self.upload(); self.client.post(self.path() + '/reindex')
        class PassReranker:
            def rerank(self, query, documents, top_k=3):
                return documents[:top_k]
        class ScriptedLLM:
            def chat(self, system_prompt, user_prompt):
                if '评估器' in system_prompt:
                    return 'YES'
                if '问答助手' in system_prompt:
                    return '报销需要财务审批。[1]'
                return '报销审批'
        store = self.service.stores[self.service.list_bases()[0]['collection']]
        store.search = lambda query, top_k=3: [{'chunk_id': c.metadata['chunk_id'], 'document': c, 'score': 1.0} for c in store.chunks[:top_k]]
        self.service.reranker = PassReranker()
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test-placeholder'}), patch('src.services.agent_service.LLMClient', ScriptedLLM):
            response = self.client.post('/api/v1/ask', json={'question': '如何报销？', 'knowledge_base_id': self.kb})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['citation_valid'])
        self.assertTrue(response.json()['sources'][0]['content'])
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': ''}):
            self.assertEqual(self.client.post('/api/v1/ask', json={'question': '问题', 'knowledge_base_id': self.kb}).status_code, 503)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/static/app.js').status_code, 200)
        self.assertEqual(self.client.get('/health').json()['documents'], 1)


if __name__ == '__main__':
    unittest.main()
