"""Exercise the production FATX counted-string normalizer, including its bounds."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SavePathTests(unittest.TestCase):
    def test_counted_path_contract(self):
        patch = (ROOT / 'patches/roswell/0113-fatx-save-path-separators.patch').read_text()
        added = '\n'.join(line[1:] for line in patch.splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        function = re.search(r'static NTSTATUS\nVfatNormalizeFatxPath\([^\n]+\)\n\{.*?\n\}',
                             added, re.S).group(0)
        harness = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint16_t USHORT, WCHAR;
typedef int32_t NTSTATUS;
typedef struct { USHORT Length, MaximumLength; WCHAR *Buffer; } UNICODE_STRING, *PUNICODE_STRING;
#define STATUS_SUCCESS 0
#define STATUS_OBJECT_NAME_INVALID ((NTSTATUS)0xc0000033)
'''+function+r'''
static void check(const char *input, const char *want, NTSTATUS status) {
    WCHAR storage[128], before[128];
    size_t n=strlen(input), expected=strlen(want);
    for(unsigned i=0;i<128;i++)storage[i]=0xa55a;
    for(unsigned i=0;i<n;i++)storage[i+1]=(unsigned char)input[i];
    memcpy(before,storage,sizeof(storage));
    UNICODE_STRING name={(USHORT)(n*2),(USHORT)(n*2),storage+1};
    assert(VfatNormalizeFatxPath(&name)==status);
    assert(storage[0]==0xa55a && storage[n+1]==0xa55a);
    assert(name.MaximumLength==n*2 && name.Buffer==storage+1);
    if(status) {assert(name.Length==n*2);assert(!memcmp(storage,before,sizeof(storage)));}
    else {
        assert(name.Length==expected*2);
        for(unsigned i=0;i<expected;i++)assert(storage[i+1]==(unsigned char)want[i]);
        assert(VfatNormalizeFatxPath(&name)==0 && name.Length==expected*2);
    }
}
int main(void) {
    check("", "", 0);
    check("\\", "\\", 0);
    check("\\slot\\file", "\\slot\\file", 0);
    check("\\slot\\\\file", "\\slot\\file", 0);
    check("slot\\\\file", "slot\\file", 0);
    check("\\slot\\\\", "\\slot\\", 0);
    check("\\slot\\\\a\\\\b", "\\slot\\a\\b", 0);
    check("\\\\slot", "", STATUS_OBJECT_NAME_INVALID);
    check("\\slot\\\\\\file", "", STATUS_OBJECT_NAME_INVALID);
    check("\\slot\\\\file\\\\\\", "", STATUS_OBJECT_NAME_INVALID);
    check("\\slot\\.\\..\\file", "\\slot\\.\\..\\file", 0);
    WCHAR unicode[]={0x3bb,'\\','\\',0x4e00,0xbeef};
    UNICODE_STRING name={8,8,unicode};
    assert(VfatNormalizeFatxPath(&name)==0 && name.Length==6);
    assert(unicode[0]==0x3bb && unicode[1]=='\\' && unicode[2]==0x4e00 && unicode[4]==0xbeef);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)/'contract.c'
            binary = Path(temporary)/'contract'
            source.write_text(harness)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
