"""Print complete generated conversations without judge decisions."""
import argparse
from dfm12.io import rows
from scripts.dfm16_role_pilot import ROOT

def main():
 p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=0);p.add_argument('--count',type=int,default=2);a=p.parse_args()
 packet=sorted(rows(ROOT/'generation-blind-packet.jsonl'),key=lambda r:r['id'])
 for i,r in enumerate(packet[a.start:a.start+a.count],a.start):
  print('\nBEGIN',i,r['id'],r['language'],r['task'])
  seen={r['seed']:'original supplied seed'}
  if not r['candidate']:print('NO CANDIDATE',r['error']);continue
  for j,m in enumerate(r['candidate']['messages']):
   print('TURN',j,m['role'],'WORDS',len(m['content'].split()),'CHARS',len(''.join(m['content'].split())))
   for paragraph in m['content'].split('\n\n'):
    if paragraph in seen:print('[verbatim '+seen[paragraph]+']')
    else:print(paragraph);seen[paragraph]=f'turn {j}'
  print('END',i,r['id'])
if __name__=='__main__':main()
