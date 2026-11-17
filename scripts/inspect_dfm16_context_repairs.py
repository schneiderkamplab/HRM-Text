"""Blind repair packets: full repaired content plus original-to-repair differences."""
import argparse
import difflib

from dfm12.io import rows
from scripts.dfm16_story_calibration import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=int,default=0)
    parser.add_argument('--count',type=int,default=5)
    args=parser.parse_args()
    stage=ROOT/'development'
    labels={r['id']:r for r in rows(stage/'manual-labels.jsonl')}
    packets=list(rows(stage/'repair-blind-packet.jsonl'))
    packets.sort(key=lambda r:labels[r['id']]['study_id'])
    for index,r in enumerate(packets[args.start:args.start+args.count],args.start):
        original,repaired=r['original'],r['repaired'];label=labels[r['id']]
        print('\n===== REPAIR',index,label['study_id'],repaired['language'],repaired['task'])
        print('ORIGINAL FLAGGED DEFECTS:',label['defects'])
        seen={}
        for key,text in [('SEED',repaired['seed'])]+[(f'TURN {i} {m["role"]}',m['content']) for i,m in enumerate(repaired['messages'])]:
            print(key, "WORDS",len(text.split()),"NONSPACE_CHARS",len("".join(text.split())))
            for i,paragraph in enumerate(text.split('\n\n')):
                if paragraph in seen: print('[verbatim as '+seen[paragraph]+']')
                else:
                    print(paragraph);seen[paragraph]=f'{key}, paragraph {i}'
        before=['SEED\n'+original['seed']]+[f'TURN {i} {m["role"]}\n'+m['content'] for i,m in enumerate(original['messages'])]
        after=['SEED\n'+repaired['seed']]+[f'TURN {i} {m["role"]}\n'+m['content'] for i,m in enumerate(repaired['messages'])]
        print('ORIGINAL DIFFERENCES (minus original, plus repair):')
        for line in difflib.unified_diff('\n\n'.join(before).splitlines(),'\n\n'.join(after).splitlines(),n=0):
            if line.startswith('-') and not line.startswith('---'): print(line)
        print('END REPAIR',index,label['study_id'])


if __name__=='__main__':main()
