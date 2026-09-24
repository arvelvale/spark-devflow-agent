import urllib.request,json
def call(path,data=None):
 r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/api/'+path,data=json.dumps(data).encode() if data else None,headers={'Content-Type':'application/json'}),timeout=180)
 return json.load(r)
m='qwen3.8:27b'
d=call('show',{'model':m})
print(json.dumps({k:d.get(k) for k in ['details','capabilities','parameters']},ensure_ascii=False))
print(json.dumps({k:v for k,v in d.get('model_info',{}).items() if any(s in k for s in ['architecture','name','parameter_count','context_length'])},ensure_ascii=False))
print(json.dumps(call('generate',{'model':m,'prompt':'请用中文简短回答：17乘以19等于多少？','stream':False,'think':False,'options':{'num_ctx':4096,'num_predict':128,'temperature':0}}),ensure_ascii=False))
print(json.dumps(call('ps'),ensure_ascii=False))
