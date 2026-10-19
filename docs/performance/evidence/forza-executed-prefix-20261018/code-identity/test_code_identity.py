# SPDX-License-Identifier: MIT
import struct,unittest
import check_code_identity as proof
class CodeIdentityTests(unittest.TestCase):
 def memory(self):return bytearray(0x10000)
 def test_small_page(self):
  ram=self.memory();va=0x84002600
  struct.pack_into('<I',ram,0x1000+((va>>22)&1023)*4,0x2001)
  struct.pack_into('<I',ram,0x2000+((va>>12)&1023)*4,0xff024001)
  self.assertEqual(proof.translate(ram,0x1000,va),0xff024600)
 def test_large_page(self):
  ram=self.memory();struct.pack_into('<I',ram,0x1000,0x04000081)
  self.assertEqual(proof.translate(ram,0x1000,0x1234),0x04001234)
  struct.pack_into('<I',ram,0x1000,0x04002081)
  with self.assertRaises(ValueError):proof.translate(ram,0x1000,0)
 def test_missing_and_bounds(self):
  ram=self.memory()
  for cr3,va in [(0,0),(len(ram),0),(0,-1),(0,2**32)]:
   with self.assertRaises(ValueError):proof.translate(ram,cr3,va)
  struct.pack_into('<I',ram,0,0x2001)
  with self.assertRaises(ValueError):proof.translate(ram,0,0)
 def test_flash_mirror(self):
  flash=bytes(range(256))*2048;ram=self.memory()
  for address in [0xff000000,0xff080000,0xfff00000]:
   data,kind=proof.backing(ram,flash,address+3,10)
   self.assertEqual(data,flash[3:13]);self.assertEqual(kind,'rom')
 def test_reject_overlay_unknown_crossing(self):
  for address,size in [(0xfffff000,4),(0x80000000,4),(0xff000fff,2),(0,-1)]:
   with self.assertRaises(ValueError):proof.backing(self.memory(),b'x'*524288,address,size)
  with self.assertRaises(ValueError):proof.backing(self.memory(),b'x',0xff000000,1)
 def test_ram_read(self):
  ram=self.memory();ram[20:24]=b'test'
  self.assertEqual(proof.backing(ram,b'',20,4),(b'test','ram'))
 def test_bad_pe(self):
  with self.assertRaises(ValueError):list(proof.sections(b''))
  with self.assertRaises(ValueError):list(proof.sections(b'MZ'+bytes(100)))
 def test_wrong_inputs_fail_closed(self):
  with self.assertRaises(ValueError):proof.compare(b'ram',b'flash',b'image')
if __name__=='__main__':unittest.main()
