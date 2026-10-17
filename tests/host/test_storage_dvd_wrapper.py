"""Synthetic XISO metadata and opaque payloads; no native execution."""
import hashlib,importlib.util,pathlib,struct,tempfile,unittest
SOURCE=pathlib.Path(__file__).parents[2]/'tests/xbe/storage-perf/make-dvd-wrapper.py'
def subject():
 spec=importlib.util.spec_from_file_location('wrapper_subject',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class DvdWrapperTests(unittest.TestCase):
 def image(self,path):
  image=bytearray(40*2048);magic=b'MICROSOFT*XBOX*MEDIA';image[32*2048:32*2048+20]=magic;image[32*2048+2028:33*2048]=magic
  struct.pack_into('<II',image,32*2048+20,34,64)
  for offset,name,sector,payload,left,right in [(0,b'default.xbe',35,b'own recorder',0,8),(32,b'target.xbe',36,b'opaque original target',0,0)]:
   position=34*2048+offset;struct.pack_into('<HHIIBB',image,position,left,right,sector,len(payload),32,len(name));image[position+14:position+14+len(name)]=name;image[sector*2048:sector*2048+len(payload)]=payload
  path.write_bytes(image);return image
 def test_layout_reports_separate_exact_boot_and_target_extents(self):
  self.assertTrue(SOURCE.exists(),'owned fixed wrapper builder missing');m=subject()
  with tempfile.TemporaryDirectory() as work:
   path=pathlib.Path(work)/'own.iso';self.image(path);value=m.inspect_wrapper(path)
   self.assertEqual(value['files']['default.xbe']['sector'],35);self.assertEqual(value['files']['target.xbe']['sector'],36)
   self.assertEqual(value['files']['target.xbe']['sha256'],hashlib.sha256(b'opaque original target').hexdigest())
 def test_layout_rejects_wrong_magic_cycles_duplicate_names_and_overlaps(self):
  self.assertTrue(SOURCE.exists(),'owned fixed wrapper builder missing');m=subject()
  with tempfile.TemporaryDirectory() as work:
   path=pathlib.Path(work)/'own.iso';original=self.image(path)
   for fault in ['magic','cycle','duplicate','overlap','extent','directory']:
    data=bytearray(original)
    if fault=='magic':data[32*2048]=0
    elif fault=='cycle':struct.pack_into('<H',data,34*2048+32+2,8)
    elif fault=='duplicate':data[34*2048+32+13]=11;data[34*2048+32+14:34*2048+32+25]=b'default.xbe'
    elif fault=='overlap':struct.pack_into('<I',data,34*2048+32+4,35)
    elif fault=='extent':struct.pack_into('<I',data,34*2048+32+8,1<<24)
    else:data[34*2048+32+12]=16
    path.write_bytes(data)
    with self.subTest(fault=fault),self.assertRaises(ValueError):m.inspect_wrapper(path)
if __name__=='__main__':unittest.main()
