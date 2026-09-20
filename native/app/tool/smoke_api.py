import urllib.request,urllib.error,urllib.parse,json,time,concurrent.futures,http.client,socket
import argparse
parser=argparse.ArgumentParser(description='Real-model local API smoke checks; uses Mimir chat messages.')
parser.add_argument('--url',default='http://127.0.0.1:8080/v1')
args=parser.parse_args()
base=args.url.rstrip('/')
for _ in range(120):
 try:
  models=json.load(urllib.request.urlopen(base+'/models',timeout=1));break
 except (OSError,urllib.error.URLError):time.sleep(1)
else:raise RuntimeError('Server did not start')
print('models',models,flush=True)
def call(extra={}):
 body={'model':'dfm-mimir','messages':[{'role':'system','content':'Answer briefly in Danish.'},{'role':'user','content':'Hvad er 2 + 2?'}],'max_tokens':16,**extra}
 req=urllib.request.Request(base+'/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as response:return response.read().decode()
a=json.loads(call());assert a['object']=='chat.completion' and a['choices'][0]['message']['content'];assert a['usage']['prompt_tokens']>0;print('nonstream',a,flush=True)
s=call({'stream':True,'stream_options':{'include_usage':True}});assert 'data: [DONE]' in s and 'chat.completion.chunk' in s;print('stream passed',flush=True)
a=json.loads(call({'temperature':.8,'top_p':.9,'seed':123}));b=json.loads(call({'temperature':.8,'top_p':.9,'seed':123}));assert a['choices']==b['choices'];print('seeded sampling repeat passed',flush=True)
with concurrent.futures.ThreadPoolExecutor(2) as pool:
 futures=[pool.submit(call,{'max_tokens':8}) for _ in range(2)]
 for f in futures:assert json.loads(f.result())['choices']
print('concurrent requests passed',flush=True)
try:call({'tools':[]})
except urllib.error.HTTPError as e:assert e.code==400
else:raise AssertionError('Unsupported field accepted')
try:call({'messages':[{'role':'user','content':'hello '*4000}]})
except urllib.error.HTTPError as e:assert e.code==400
else:raise AssertionError('Overflow accepted')
print('validation and overflow passed',flush=True)
address=urllib.parse.urlparse(base)
conn=http.client.HTTPConnection(address.hostname,address.port,timeout=30)
conn.request('POST','/v1/chat/completions',body=json.dumps({'model':'dfm-mimir','messages':[{'role':'user','content':'Write a very long story.'}],'max_tokens':512,'stream':True}),headers={'Content-Type':'application/json'})
r=conn.getresponse();assert r.status==200
print('stream before disconnect',r.readline(),flush=True)
conn.sock.shutdown(socket.SHUT_RDWR) if conn.sock else None
r.close();conn.close()
start=time.monotonic();assert json.loads(call({'max_tokens':4}))['choices'];elapsed=time.monotonic()-start
print('recovery after disconnect',elapsed,flush=True);assert elapsed<30
print('REAL API CHECKS PASSED',flush=True)
