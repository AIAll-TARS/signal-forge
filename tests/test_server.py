import json, tempfile, threading, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch
from signal_forge.server import Handler, ThreadingHTTPServer
from signal_forge.store import Store

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.db=str(Path(self.temp.name)/'ui.db')
        s=Store(self.db);s.init(); sid,_=s.add_source({'name':'Official feed','url':'https://example.test/feed','authority':'primary','scan_method':'rss','topics':['policy']}); iid,_=s.add_item({'source_id':sid,'title':'Poland biomethane regulation','url':'https://example.test/item','content':'Poland biomethane regulation grid project'}); from signal_forge.scoring import Analyst; s.save_analysis(iid,Analyst().analyze(dict(s.unanalysed()[0])));s.close()
        Handler.db_path=self.db; self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler); self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self): self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def test_health_status(self):
        with urlopen(self.base+'/api/health') as r: data=json.load(r)
        self.assertTrue(data['ok']);self.assertEqual(data['metrics']['sources'],1);self.assertEqual(data['metrics']['items'],1)
    def test_dashboard_shell(self):
        with urlopen(self.base+'/') as r: html=r.read().decode()
        self.assertIn('SIGNAL FORGE',html);self.assertIn('Galia Green Power',html);self.assertIn('/api/scan',html);self.assertIn('/api/ingest',html)
    def test_manual_ingest(self):
        captured={'title':'Biomethane tender','url':'https://example.test/article','content':'Poland biomethane tender','topics':['projects-transactions']}
        request=Request(self.base+'/api/ingest',data=json.dumps({'url':captured['url'],'topics':captured['topics']}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with patch('signal_forge.server.ingest_url',return_value=captured):
            with urlopen(request) as response: result=json.load(response)
        self.assertTrue(result['created'])
if __name__=='__main__':unittest.main()
