import json
import tempfile
import unittest
from pathlib import Path
from release_evidence.cli import create, verify, main, EvidenceError

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'release'
        self.root.mkdir()
        (self.root / 'a.txt').write_text('original')
        self.manifest = self.base / 'manifest.json'
        self.sha = create(self.root, 'v1', self.manifest, [{'name':'tests','status':'passed'}])
    def edit(self, fn):
        data = json.loads(self.manifest.read_text()); fn(data)
        self.manifest.write_text(json.dumps(data))
    def test_match(self):
        self.assertTrue(verify(self.root, self.manifest, self.sha)['ok'])
    def test_modified(self):
        (self.root / 'a.txt').write_text('modified')
        self.assertFalse(verify(self.root, self.manifest)['ok'])
    def test_missing(self):
        (self.root / 'a.txt').unlink()
        self.assertEqual(verify(self.root, self.manifest)['issues'], ['missing: a.txt'])
    def test_extra(self):
        (self.root / 'extra').write_text('x')
        self.assertEqual(verify(self.root, self.manifest)['issues'], ['unexpected: extra'])
    def test_manifest_tamper(self):
        self.edit(lambda d: d.update(release_version='v2'))
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest,self.sha)
    def test_duplicate_path(self):
        self.edit(lambda d: d['files'].append(d['files'][0]))
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_path_traversal(self):
        self.edit(lambda d: d['files'][0].update(path='../secret'))
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_absolute_path(self):
        self.edit(lambda d: d['files'][0].update(path='/secret'))
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_symlink(self):
        (self.root / 'link').symlink_to(self.manifest)
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError): create(self.root,'v2',self.manifest)
    def test_empty_release(self):
        (self.root / 'a.txt').unlink()
        with self.assertRaises(EvidenceError): create(self.root,'v2',self.base/'new.json')
    def test_output_inside(self):
        with self.assertRaises(EvidenceError): create(self.root,'v2',self.root/'m.json')
    def test_bad_schema(self):
        self.edit(lambda d: d.update(schema_version=2))
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_bad_size(self):
        self.edit(lambda d: d['files'][0].update(size=True))
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_bad_check(self):
        with self.assertRaises(EvidenceError): create(self.root,'v2',self.base/'new.json',[{'name':'x','status':'maybe'}])
    def test_duplicate_json_key(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(EvidenceError): verify(self.root,self.manifest)
    def test_binary_nested_unicode(self):
        (self.root/'nested').mkdir()
        (self.root/'nested'/'é.bin').write_bytes(bytes(range(256)))
        m=self.base/'new.json'; s=create(self.root,'v2',m)
        self.assertTrue(verify(self.root,m,s)['ok'])
    def test_cli_codes(self):
        self.assertEqual(main(['verify',str(self.root),'--manifest',str(self.manifest)]),0)
        (self.root/'a.txt').write_text('changed')
        self.assertEqual(main(['verify',str(self.root),'--manifest',str(self.manifest)]),1)
        self.assertEqual(main(['verify',str(self.root),'--manifest',str(self.base/'none')]),2)
if __name__ == '__main__': unittest.main()
