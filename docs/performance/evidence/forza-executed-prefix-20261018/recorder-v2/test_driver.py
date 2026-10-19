# SPDX-License-Identifier: MIT
import hashlib,importlib.util,json,os,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
cases={
 'recorder':'partial fault rep zero_rep switch same_pc exit_before_entry aggregate alias invalid unknown desc_overflow insn_overflow row_overflow decode_rollback wrong_count excluded excluded_transition excluded_alias outside_instruction contiguity bad_instruction bad_segment unfinished rep_regression empty_rep bad_type unknown_flush unfinished_output bounded_samples output'.split(),
 'integration':'thread_switch dpc_same_thread mismatch failed_switch_read inactive_reanchor admission slots'.split()}
helper=(HERE/'staged/target/i386/tcg/misc_helper.c').read_text()
start=helper.index('/* SPDX-License-Identifier: MIT\n * Independently authored, baseline-add882 scalar identity observer.')
end=helper.index('void helper_spirit_menu_trace(CPUX86State *env, uint32_t pc)',start)
(HERE/'actual-identity-fragment.c').write_text(helper[start:end])
results=[]
with tempfile.TemporaryDirectory(prefix='forza-prefix-tests-') as temp:
 for sanitizer in ['', '-fsanitize=address,undefined']:
  for unit,names in cases.items():
   exe=Path(temp)/unit
   cmd=['clang','-std=c11','-O2','-g','-Wall','-Wextra','-Werror']+([sanitizer] if sanitizer else [])+[str(HERE/f'test_{unit}.c'),'-o',str(exe)]
   subprocess.run(cmd,check=True)
   for name in names:
    subprocess.run([str(exe),name],check=True,stdout=subprocess.DEVNULL)
   results.append({'unit':unit,'sanitizer':sanitizer or 'none','passed':len(names)})
 for sanitizer in ['', '-fsanitize=address,undefined']:
  exe=Path(temp)/'actual_identity'
  cmd=['clang','-std=c11','-O2','-g','-Wall','-Wextra','-Werror']+([sanitizer] if sanitizer else [])+[str(HERE/'test_actual_identity.c'),'-o',str(exe)]
  subprocess.run(cmd,check=True);subprocess.run([str(exe)],check=True)
  results.append({'unit':'actual_identity_admission_and_drain','sanitizer':sanitizer or 'none','passed':1})
 # Real recorder output independently parsed by root's schema validator.
 output=subprocess.check_output([str(Path(temp)/'recorder'),'output'],text=True)
 spec=importlib.util.spec_from_file_location('prefix',Path(os.environ['PREFIX_ANALYZER']))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 capture=module.parse(output);assert capture['rows'][0]['begun']==2
 assert capture['rows'][0]['rep_iterations']==7
 (HERE/'synthetic-prefix.log').write_text(output)
# Generated-code ordering guards: attempted ordinal before decode; no metadata on rollback;
# both REP bodies increment after the body and before ECX update.
t=(HERE/'staged/target/i386/tcg/translate.c').read_text()
assert t.index('forza_prefix_store(1,dc->base.num_insns)')<t.index('switch (sigsetjmp(dc->jmpbuf, 0))')
rollback=t[t.index('    case 2:',t.index('switch (sigsetjmp(dc->jmpbuf, 0))')):]
rollback=rollback[:rollback.index('    default:')]
assert 'return;' in rollback and 'forza_prefix_instruction' not in rollback
assert t.count('fn(s, ot, dshift);\n    forza_prefix_rep_body(s);')==2
assert t.index('forza_prefix_instruction(dc->prefix_tb_id')>t.index('switch (sigsetjmp(dc->jmpbuf, 0))')
assert 'dc->base.pc_next==0x84001198' in t
assert t.count('gen_helper_forza_prefix_tb(')==1
results.append({'unit':'source_order_and_real_output_parser','passed':7})
(HERE/'test-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
