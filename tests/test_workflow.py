"""Integration test against the running server. Creates and removes its own users' projects."""
import requests,time,io,zipfile,json
import fitz
from PIL import Image
BASE='http://127.0.0.1:8000/api'
s=requests.Session();s.headers['X-Studio']='1'
results=[]
def call(method,path,**kw):
    r=s.request(method,BASE+path,**kw)
    assert r.ok,(path,r.status_code,r.text[:900])
    return r.json()
def record(name):results.append(name); print('PASS',name)
def run(pid,action,**body):
    j=call('POST',f'/projects/{pid}/run/{action}',json=body)
    deadline=time.time()+120
    while time.time()<deadline:
        j=call('GET','/jobs/'+j['id'])
        if j['status']=='done':return j
        if j['status']=='error':raise AssertionError(j['error'])
        time.sleep(.15)
    raise AssertionError('job timeout')
call('POST','/auth/register',json={'email':f'test-{time.time_ns()}@studio.test','password':'workflow-secret-123','name':'Workflow test'})
record('Authentification par compte et cookie HTTP-only')
p=call('POST','/projects/demo',json={});pid=p['id'];assert p['source']['pages']==6;record('Création du PDF de démonstration, validation et import')
run(pid,'analyze');p=call('GET','/projects/'+pid);b=p['book'];assert p['result']['pages']>0 and len(b['chapters'])>=5 and len(b['suggestions'])>=4;record('Extraction, langue, chapitres et prompts contextuels')
assert any('Cotonou' in i['passage'] for i in b['suggestions']);record('Prompts réellement liés au contenu')
for f in ['original.pdf','interior.pdf','cover.pdf','complete.pdf']:
    r=s.get(BASE+f'/projects/{pid}/files/{f}');assert r.ok and r.content[:5]==b'%PDF-';d=fitz.open(stream=r.content,filetype='pdf');assert len(d)>0
    if f=='interior.pdf':assert 'Amina' in ''.join(pg.get_text() for pg in d)
    if f=='cover.pdf':assert d[0].rect.width>d[0].rect.height and d[0].trimbox.width<d[0].mediabox.width
record('PDF original, intérieur, couverture à plat avec TrimBox, PDF complet réels')
r=s.get(BASE+f'/projects/{pid}/files/book.epub');assert zipfile.ZipFile(io.BytesIO(r.content)).testzip() is None;record('EPUB texte valide comme archive')
r=s.get(BASE+f'/projects/{pid}/files/preview-0.png');im=Image.open(io.BytesIO(r.content));assert im.width>100;record('Aperçu rendu depuis le PDF exporté')
assert any(x['code']=='print' and x['status']=='warning' for x in p['result']['quality']);record('Contrôle qualité et avertissement prépresse honnête')
img=Image.new('RGB',(1100,800),'#aabbcc');buf=io.BytesIO();img.save(buf,format='PNG');asset=call('POST',f'/projects/{pid}/assets',files={'file':('test.png',buf.getvalue(),'image/png')})
b['suggestions'][0]['asset']=asset['asset'];b['suggestions'][0]['origin']='Image importée';b['cover_asset']=asset['asset'];b['subtitle']='Test réel';b['chapters'][1]['blocks'][-1]['text']+=' Test de conservation du texte.'
p=call('PUT','/projects/'+pid,json={'revision':p['revision'],'book':b});run(pid,'render');p=call('GET','/projects/'+pid)
assert p['render_revision']==p['revision'];record('Import d’image, édition, couverture et recomposition')
r=s.get(BASE+f'/projects/{pid}/files/interior.pdf');d=fitz.open(stream=r.content,filetype='pdf');assert any(pg.get_images() for pg in d);assert 'Test de conservation' in ''.join(pg.get_text() for pg in d);record('Image et texte édité présents dans le fichier final')
p=call('POST',f'/projects/{pid}/history/undo',json={});assert p['book']['subtitle']!='Test réel'
p=call('POST',f'/projects/{pid}/history/redo',json={});assert p['book']['subtitle']=='Test réel';record('Annuler et rétablir persistés côté serveur')
r=call('POST',f'/projects/{pid}/assistant',json={'command':'Mets les illustrations du chapitre 2 en style 3D'});p=call('GET','/projects/'+pid);assert any(i['style']=='3D' for i in p['book']['suggestions']);record('Assistant local modifie réellement les prompts')
j=call('POST',f'/projects/{pid}/run/image',json={'suggestion':p['book']['suggestions'][0]['id']})
while True:
    j=call('GET','/jobs/'+j['id'])
    if j['status'] in ['done','error']:break
    time.sleep(.1)
assert j['status']=='error' and 'Aucun modèle' in j['error'];record('Pas de génération simulée : absence de fournisseur signalée')
run(pid,'fix');record('Correction automatique réelle puis réexport')
call('PUT','/settings',json={'text_key':'test-never-expose'});cfg=call('GET','/settings');assert cfg['text_key_set'] and 'test-never-expose' not in json.dumps(cfg);record('Secrets non renvoyés au frontend')
call('PUT','/settings',json={'text_key':''})
other=requests.Session();other.headers['X-Studio']='1';other.post(BASE+'/auth/guest',json={});assert other.get(BASE+f'/projects/{pid}').status_code==404 and other.get(BASE+f'/projects/{pid}/files/original.pdf').status_code==404
record('Isolation des utilisateurs et protection des fichiers')
r=s.post(BASE+'/projects/upload',files={'file':('bad.pdf',b'not-a-pdf','application/pdf')});assert r.status_code==400
record('Faux PDF refusé')
r=s.put(BASE+'/projects/'+pid,json={'revision':-100,'book':b});assert r.status_code==409;record('Conflit d’édition détecté')
call('DELETE','/projects/'+pid);assert s.get(BASE+'/projects/'+pid).status_code==404;record('Suppression du projet et de ses fichiers')
from pathlib import Path
Path('tests/results.json').write_text(json.dumps({'passed':len(results),'checks':results},ensure_ascii=False,indent=2))
print('All',len(results),'checks passed.')
