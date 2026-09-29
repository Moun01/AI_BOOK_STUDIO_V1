import os, json, sqlite3, secrets, hashlib, hmac, time, uuid, shutil, threading, re, io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import fitz
from .engines import extract_pdf, analyze_document, build_prompts, export_book, create_demo, STYLES
from .providers import LocalImageProvider, TextProvider

ROOT=Path(__file__).resolve().parent.parent; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True); os.chmod(DATA,0o700)
DB=DATA/'studio.sqlite3'
app=FastAPI(title='AI BOOK STUDIO',docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
executor=ThreadPoolExecutor(max_workers=2); lock=threading.RLock()

def db():
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT,name TEXT,settings TEXT DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);
    CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,user_id TEXT,data TEXT);
    CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,user_id TEXT,project_id TEXT,data TEXT);''')
    # Interrupted jobs are not silently reported as completed.
    for row in c.execute('SELECT id,data FROM jobs').fetchall():
        j=json.loads(row['data'])
        if j.get('status') in ['queued','running']:
            j.update(status='error',error='Traitement interrompu au redémarrage. Relancez l’opération.'); c.execute('UPDATE jobs SET data=? WHERE id=?',(json.dumps(j),row['id']))
os.chmod(DB,0o600)

@app.middleware('http')
async def protect(request,call_next):
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-studio')!='1':
        return JSONResponse({'detail':'En-tête de sécurité manquant.'},403)
    try: response=await call_next(request)
    except Exception: return JSONResponse({'detail':'Erreur interne. Consultez les journaux du serveur.'},500)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

def user(req):
    token=req.cookies.get('studio_session',''); hashed=hashlib.sha256(token.encode()).hexdigest()
    with db() as c: row=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(hashed,time.time())).fetchone()
    if not row: raise HTTPException(401,'Connectez-vous pour accéder à votre espace.')
    return dict(row)

def public_user(u): return {k:u[k] for k in ['id','email','name']}

def session(u,req):
    token=secrets.token_urlsafe(40)
    with db() as c: c.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+604800))
    secure=req.url.scheme=='https' or req.headers.get('x-forwarded-proto','').split(',')[0].strip()=='https' or req.headers.get('host','').endswith('.e2b.app')
    response=JSONResponse(public_user(u))
    # HTTPS previews are embedded cross-site. CHIPS isolates the cookie by the
    # top-level site; custom mutation headers and no CORS protect against CSRF.
    response.set_cookie('studio_session',token,max_age=604800,httponly=True,samesite='none' if secure else 'lax',secure=secure)
    if secure: response.headers['set-cookie']+='; Partitioned'
    return response

def password_hash(p,salt=None):
    salt=salt or secrets.token_hex(16); return salt+':'+hashlib.scrypt(p.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()

attempts={}
@app.post('/api/auth/{action}')
async def auth(action:str,req:Request):
    data=await req.json(); ip=req.client.host; now=time.time(); attempts[ip]=[t for t in attempts.get(ip,[]) if t>now-60]
    if len(attempts[ip])>=20: raise HTTPException(429,'Trop de tentatives. Réessayez dans une minute.')
    attempts[ip].append(now)
    if action=='guest':
        uid=uuid.uuid4().hex; u={'id':uid,'email':None,'name':'Mon espace découverte'}
        with db() as c: c.execute('INSERT INTO users(id,email,password,name) VALUES (?,?,?,?)',(uid,None,'',u['name']))
        return session(u,req)
    email=str(data.get('email','')).strip().lower(); pw=str(data.get('password',''))
    if len(pw)>200 or len(email)>200: raise HTTPException(400,'Identifiants trop longs.')
    if action=='register':
        if len(pw)<10 or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$',email): raise HTTPException(400,'Email valide et mot de passe de 10 caractères minimum requis.')
        u={'id':uuid.uuid4().hex,'email':email,'name':str(data.get('name') or email.split('@')[0])[:60]}
        try:
            with db() as c: c.execute('INSERT INTO users(id,email,password,name) VALUES (?,?,?,?)',(u['id'],email,password_hash(pw),u['name']))
        except sqlite3.IntegrityError: raise HTTPException(409,'Cet email est déjà utilisé.')
        return session(u,req)
    if action=='login':
        with db() as c: row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if not row or not row['password'] or not hmac.compare_digest(row['password'],password_hash(pw,row['password'].split(':')[0])): raise HTTPException(401,'Email ou mot de passe incorrect.')
        return session(dict(row),req)
    raise HTTPException(404)

@app.post('/api/logout')
def logout(req:Request):
    with db() as c: c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(req.cookies.get('studio_session','').encode()).hexdigest(),))
    r=JSONResponse({'ok':True}); r.delete_cookie('studio_session'); return r

@app.get('/api/me')
def me(req:Request): return public_user(user(req))

@app.put('/api/me')
async def update_me(req:Request):
    u=user(req)
    data=await req.json()

    name=str(data.get('name','')).strip()
    email=str(data.get('email','')).strip().lower()

    if not name or len(name)>60:
        raise HTTPException(400,'Le nom est requis et doit contenir 60 caractères maximum.')

    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$',email) or len(email)>200:
        raise HTTPException(400,'Veuillez saisir une adresse email valide.')

    try:
        with db() as c:
            c.execute(
                'UPDATE users SET name=?, email=? WHERE id=?',
                (name,email,u['id'])
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409,'Cet email est déjà utilisé.')

    u['name']=name
    u['email']=email
    return public_user(u)

def load(pid,u):
    with db() as c: row=c.execute('SELECT data FROM projects WHERE id=? AND user_id=?',(pid,u['id'])).fetchone()
    if not row: raise HTTPException(404,'Projet introuvable.')
    return json.loads(row['data'])

def save(p,u):
    p['updated']=datetime.now(timezone.utc).isoformat()
    with db() as c: c.execute('INSERT OR REPLACE INTO projects VALUES (?,?,?)',(p['id'],u['id'],json.dumps(p,ensure_ascii=False)))

def public_project(p): return {k:v for k,v in p.items() if k not in ['history','future']}

def busy(p):
    if p.get('job'):
        with db() as c: row=c.execute('SELECT data FROM jobs WHERE id=?',(p['job'],)).fetchone()
        if row and json.loads(row['data'])['status'] in ['queued','running']: raise HTTPException(409,'Un traitement est en cours. Patientez avant de modifier le projet.')

def snapshot(p):
    if p.get('book'): p['history']=(p.get('history',[])+[p['book']])[-30:]; p['future']=[]

def new_project(u,filename,rawbytes):
    with db() as c: count=c.execute('SELECT count(*) FROM projects WHERE user_id=?',(u['id'],)).fetchone()[0]
    if count>=30: raise HTTPException(400,'Limite locale : 30 projets par espace.')
    if len(rawbytes)>30*1024*1024: raise HTTPException(413,'PDF limité à 30 Mo.')
    if not rawbytes.startswith(b'%PDF-'): raise HTTPException(400,'Le fichier fourni n’est pas un PDF valide.')
    try:
        doc=fitz.open(stream=rawbytes,filetype='pdf')
        if doc.needs_pass: raise ValueError('PDF chiffré : déverrouillez-le avant importation.')
        if len(doc)<1 or len(doc)>250: raise ValueError('Le PDF doit contenir de 1 à 250 pages.')
        info={'filename':Path(filename).name,'bytes':len(rawbytes),'pages':len(doc),'title':doc.metadata.get('title') or Path(filename).stem,'author':doc.metadata.get('author') or ''}
    except Exception as e: raise HTTPException(400,str(e))
    pid=uuid.uuid4().hex; folder=DATA/pid; folder.mkdir(mode=0o700); (folder/'original.pdf').write_bytes(rawbytes)
    p={'id':pid,'created':datetime.now(timezone.utc).isoformat(),'title':info['title'],'source':info,'status':'imported','book':None,'revision':0,'render_revision':-1,'result':None,'history':[],'future':[]}; save(p,u); return p

@app.get('/api/projects')
def projects(req:Request):
    u=user(req)
    with db() as c: rows=c.execute('SELECT data FROM projects WHERE user_id=?',(u['id'],)).fetchall()
    ps=[json.loads(r['data']) for r in rows]
    return sorted([{k:p.get(k) for k in ['id','title','source','status','updated','revision','render_revision','result','job']} for p in ps],key=lambda p:p['updated'],reverse=True)

@app.post('/api/projects/upload')
async def upload(req:Request,file:UploadFile=File(...)):
    u=user(req); data=await file.read(30*1024*1024+1); return public_project(new_project(u,file.filename or 'document.pdf',data))

@app.post('/api/projects/demo')
def demo(req:Request):
    u=user(req); path=DATA/'demonstration.pdf'
    if not path.exists(): create_demo(path)
    return public_project(new_project(u,'Entreprendre autrement.pdf',path.read_bytes()))

@app.get('/api/projects/{pid}')
def project(pid:str,req:Request): return public_project(load(pid,user(req)))

@app.delete('/api/projects/{pid}')
def delete(pid:str,req:Request):
    u=user(req)
    with lock:
        p=load(pid,u); busy(p)
        with db() as c: c.execute('DELETE FROM projects WHERE id=?',(pid,)); c.execute('DELETE FROM jobs WHERE project_id=?',(pid,))
        shutil.rmtree(DATA/pid,ignore_errors=True)
    return {'ok':True}

def validate_book(b,folder):
    try:
        if not isinstance(b['title'],str) or not 1<=len(b['title'])<=180: raise ValueError('Titre requis, 180 caractères maximum.')
        for key,limit in [('subtitle',250),('author',100),('summary',1300),('author_bio',450)]:
            if not isinstance(b.get(key,''),str) or len(b.get(key,''))>limit: raise ValueError(f'{key} : maximum {limit} caractères.')
        s=b['settings']
        if s['format'] not in ['A4','A5','6 × 9','Personnalisé']: raise ValueError('Format inconnu.')
        for k,lo,hi in [('width',100,320),('height',140,450),('margin',10,35),('font_size',8,16),('paper',.05,.3),('bleed',0,6)]:
            v=float(s[k])
            if not lo<=v<=hi: raise ValueError(f'Valeur {k} hors limites ({lo}–{hi}).')
        if s['font'] not in ['StudioSerif','StudioSans'] or not re.match(r'^#[a-fA-F0-9]{6}$',s['accent']): raise ValueError('Police ou couleur invalide.')
        if s['image_style'] not in STYLES: raise ValueError('Style invalide.')
        if len(b['chapters'])>250 or sum(len(c['blocks']) for c in b['chapters'])>8000: raise ValueError('Structure trop volumineuse.')
        for c in b['chapters']:
            for x in c['blocks']:
                if not isinstance(x['text'],str) or len(x['text'])>100000: raise ValueError('Bloc de texte invalide.')
        for asset in [b.get('cover_asset')]+[i.get('asset') for i in b['suggestions']]:
            if asset and (not re.match(r'^[a-f0-9]{32}\.png$',asset) or not (folder/asset).is_file()): raise ValueError('Image invalide.')
        for i in b['suggestions']:
            if not 20<=float(i.get('width_pct',85))<=100: raise ValueError('Largeur d’image : 20–100 %.')
    except (KeyError,TypeError) as e: raise ValueError('Structure du livre invalide.')

@app.put('/api/projects/{pid}')
async def update(pid:str,req:Request):
    u=user(req); data=await req.json()
    if len(json.dumps(data))>8_000_000: raise HTTPException(413,'Projet trop volumineux.')
    with lock:
        p=load(pid,u); busy(p)
        if data.get('revision')!=p['revision']: raise HTTPException(409,'Version modifiée dans un autre onglet. Rechargez le projet.')
        try: validate_book(data['book'],DATA/pid)
        except ValueError as e: raise HTTPException(400,str(e))
        snapshot(p); p['book']=data['book']; p['title']=p['book']['title']; p['revision']+=1; save(p,u)
    return public_project(p)

@app.post('/api/projects/{pid}/history/{direction}')
def history(pid:str,direction:str,req:Request):
    u=user(req)
    with lock:
        p=load(pid,u); busy(p); src='history' if direction=='undo' else 'future'; dst='future' if direction=='undo' else 'history'
        if not p.get(src): raise HTTPException(400,'Aucune modification à '+('annuler.' if direction=='undo' else 'rétablir.'))
        p.setdefault(dst,[]).append(p['book']); p['book']=p[src].pop(); p['revision']+=1; p['title']=p['book']['title']; save(p,u)
    return public_project(p)

def job_update(jid,**kwargs):
    with db() as c:
        row=c.execute('SELECT data FROM jobs WHERE id=?',(jid,)).fetchone(); j=json.loads(row['data']); j.update(kwargs); c.execute('UPDATE jobs SET data=? WHERE id=?',(json.dumps(j),jid))

def settings(u):
    with db() as c: return json.loads(c.execute('SELECT settings FROM users WHERE id=?',(u['id'],)).fetchone()[0])

def work(jid,pid,u,action,payload):
    try:
        p=load(pid,u); folder=DATA/pid; job_update(jid,status='running',completed=0)
        if action=='analyze':
            raw=extract_pdf(folder/'original.pdf',folder); raw['filename']=p['source']['filename']; (folder/'extracted.json').write_text(json.dumps(raw,ensure_ascii=False)); job_update(jid,completed=1)
            book=analyze_document(raw); book['language']=raw['language']; snapshot(p); p['book']=book; p['source'].update({k:raw[k] for k in ['language','tables','source_images']}); job_update(jid,completed=2)
            book['suggestions']=build_prompts(book)
            if p.get('demo_asset'):
                target=next((i for i in book['suggestions'] if 'idée' in i['section'].lower()),None)
                if target:
                    target['asset']=p['demo_asset']; target['origin']='IA Arena · illustration de démonstration pré-générée'; target['caption']='Illustration générée avec Arena pour ce livre de démonstration.'
            p['revision']+=1; p['title']=book['title']; job_update(jid,completed=3)
        elif action=='image':
            book=json.loads(json.dumps(p['book'])); target=next((x for x in book['suggestions'] if x['id']==payload.get('suggestion')),None)
            if not target: raise ValueError('Illustration introuvable.')
            target['asset']=LocalImageProvider().generate(target['prompt'],settings(u),folder); target['origin']='IA'; snapshot(p); p['book']=book; p['revision']+=1; job_update(jid,completed=1)
        elif action=='text-ai':
            enriched=TextProvider().analyze(p['book'],settings(u)); snapshot(p); p['book']=json.loads(json.dumps(p['book'])); p['book'].update(enriched); p['book']['summary_method']='Résumé généré par le modèle configuré ; à vérifier.'; p['revision']+=1; job_update(jid,completed=1)
        elif action=='fix':
            snapshot(p); p['book']=json.loads(json.dumps(p['book'])); b=p['book']; b['settings']['margin']=max(18,float(b['settings']['margin'])); b['settings']['bleed']=3
            for item in b['suggestions']:
                if item.get('asset'):
                    iw=Image.open(folder/item['asset']).width
                    from .engines import page_size
                    width=page_size(b['settings'])[0]-2*b['settings']['margin']*72/25.4-12
                    item['width_pct']=max(20,min(item.get('width_pct',85),int(iw/300*72/width*100)))
            p['revision']+=1; job_update(jid,completed=1)
        elif action=='prompts':
            snapshot(p); p['book']=json.loads(json.dumps(p['book']))
            for i in p['book']['suggestions']:
                i['style']=p['book']['settings']['image_style']; i['prompt']=f'Book illustration, {i["style"]} style. Subject: {p["book"]["title"]}. Depict this exact passage: {i["passage"]}. Coherent muted palette. No text.'
            p['revision']+=1; job_update(jid,completed=1)
        if not p.get('book'): raise ValueError('Analysez d’abord le PDF.')
        job_update(jid,stage='Rendu des pages, couverture et contrôle du PDF réel')
        # Render to a staging directory. Existing exports remain intact if rendering fails.
        staging=folder/('render-'+jid); staging.mkdir()
        for f in folder.glob('*.png'):
            if re.match(r'^[a-f0-9]{32}\.png$',f.name): shutil.copyfile(f,staging/f.name)
        result=export_book(p['book'],staging)
        for f in staging.iterdir():
            if not re.match(r'^[a-f0-9]{32}\.png$',f.name): os.replace(f,folder/f.name)
        shutil.rmtree(staging)
        p['result']=result; p['render_revision']=p['revision']; p['status']='ready'; save(p,u)
        with db() as c: total=json.loads(c.execute('SELECT data FROM jobs WHERE id=?',(jid,)).fetchone()[0])['total']
        job_update(jid,status='done',completed=total,stage='Fichiers créés et contrôlés')
    except Exception as e:
        import traceback; traceback.print_exc(); job_update(jid,status='error',error=str(e)[:700])

def launch(pid,u,action,payload=None):
    with lock:
        p=load(pid,u); busy(p)
        if action!='analyze' and not p.get('book'): raise HTTPException(400,'Analysez le document avant cette opération.')
        jid=uuid.uuid4().hex; steps=['Extraction PDF','Structure locale','Prompts contextuels','Mise en page, couverture et contrôle'] if action=='analyze' else ['Traitement demandé','Rendu et contrôle'] if action!='render' else ['Rendu et contrôle']
        j={'id':jid,'project_id':pid,'status':'queued','steps':steps,'total':len(steps),'completed':0,'stage':'En attente'}
        with db() as c: c.execute('INSERT INTO jobs VALUES (?,?,?,?)',(jid,u['id'],pid,json.dumps(j)))
        p['job']=jid; save(p,u); executor.submit(work,jid,pid,u,action,payload or {}); return j

@app.post('/api/projects/{pid}/run/{action}')
async def run(pid:str,action:str,req:Request):
    if action not in ['analyze','render','image','text-ai','fix','prompts']: raise HTTPException(404)
    return launch(pid,user(req),action,await req.json())

@app.get('/api/jobs/{jid}')
def job(jid:str,req:Request):
    u=user(req)
    with db() as c: row=c.execute('SELECT data FROM jobs WHERE id=? AND user_id=?',(jid,u['id'])).fetchone()
    if not row: raise HTTPException(404)
    return json.loads(row['data'])

@app.post('/api/projects/{pid}/assets')
async def asset(pid:str,req:Request,file:UploadFile=File(...)):
    u=user(req); p=load(pid,u); busy(p); raw=await file.read(15*1024*1024+1)
    if len(raw)>15*1024*1024: raise HTTPException(413,'Image limitée à 15 Mo.')
    try:
        im=Image.open(io.BytesIO(raw))
        if im.width*im.height>35_000_000: raise ValueError('Image limitée à 35 mégapixels.')
        im.load(); name=uuid.uuid4().hex+'.png'; im.convert('RGB').save(DATA/pid/name)
    except Exception as e: raise HTTPException(400,'Image invalide : '+str(e)[:100])
    return {'asset':name,'width':im.width,'height':im.height}

@app.get('/api/projects/{pid}/files/{filename}')
def download(pid:str,filename:str,req:Request,download:int=0):
    u=user(req); p=load(pid,u)
    if not re.match(r'^(original\.pdf|interior\.pdf|cover\.pdf|complete\.pdf|book\.epub|thumb\.png|preview-\d+\.png|[a-f0-9]{32}\.png)$',filename): raise HTTPException(404)
    path=DATA/pid/filename
    if not path.is_file(): raise HTTPException(404,'Fichier non créé. Lancez le rendu.')
    return FileResponse(path,filename=filename if download else None)

@app.get('/api/settings')
def getsettings(req:Request):
    s=settings(user(req)); return {**{k:v for k,v in s.items() if not k.endswith('_key')},'text_key_set':bool(s.get('text_key')),'image_key_set':bool(s.get('image_key')),'vision_key_set':bool(s.get('vision_key'))}

@app.put('/api/settings')
async def putsettings(req:Request):
    u=user(req); data=await req.json(); s=settings(u)
    for key in ['text_provider','text_model','image_provider','text_key','image_key','vision_key']:
        if key in data and data[key] is not None:
            if len(str(data[key]))>500: raise HTTPException(400,'Paramètre trop long.')
            s[key]=str(data[key])
    if s.get('text_provider','none') not in ['none','ollama','openai'] or s.get('image_provider','none') not in ['none','a1111','openai']: raise HTTPException(400,'Fournisseur invalide.')
    with db() as c: c.execute('UPDATE users SET settings=? WHERE id=?',(json.dumps(s),u['id']))
    return {'ok':True}

@app.post('/api/projects/{pid}/assistant')
async def assistant(pid:str,req:Request):
    u=user(req); data=await req.json(); text=str(data.get('command','')).lower(); p=load(pid,u); busy(p)
    if not p.get('book'): raise HTTPException(400,'Analysez le livre avant d’utiliser les commandes.')
    if 'corrig' in text or 'réorganise' in text:
        return {'message':'Recalcul des sauts de page et des marges. Les images trop petites sont réduites ; aucune résolution artificielle n’est inventée.','job':launch(pid,u,'fix')}
    if 'couverture' in text:
        return {'message':'La couverture typographique est recalculée à partir des informations et du style actuels. Ce n’est pas une génération IA.','job':launch(pid,u,'render')}
    if ('style' in text or '3d' in text) and ('illustration' in text or 'chapitre' in text):
        style=next((s for s in STYLES if s.lower() in text),None)
        if not style: raise HTTPException(400,'Précisez un style : 3D, aquarelle, éditorial…')
        match=re.search(r'chapitre\s+(\d+)',text); index=int(match.group(1))-1 if match else None
        if index is not None and not 0<=index<len(p['book']['chapters']): raise HTTPException(400,'Chapitre introuvable dans la structure.')
        snapshot(p); p['book']=json.loads(json.dumps(p['book'])); count=0
        for i in p['book']['suggestions']:
            if index is None or i['chapter_id']==p['book']['chapters'][index]['id']:
                i['style']=style; i['prompt']=f'{style} book illustration. Depict: {i["passage"]}. No lettering.'; count+=1
        p['revision']+=1; save(p,u)
        return {'message':f'{count} prompt(s) mis à jour en style {style}. Les images existantes ne changent pas sans régénération explicite.'}
    if 'image' in text and ('change' in text or 'génère' in text or 'regen' in text):
        m=re.search(r'page\s+(\d+)',text)
        if not m: raise HTTPException(400,'Précisez la page du PDF source, par exemple « Change l’image de la page 3 ».')
        target=next((i for i in p['book']['suggestions'] if i['page']==int(m.group(1))),None)
        if not target: raise HTTPException(400,'Aucune suggestion liée à cette page source. Ajoutez-en une dans Illustrations.')
        return {'message':'Génération demandée au fournisseur configuré.','job':launch(pid,u,'image',{'suggestion':target['id']})}
    if 'ajoute' in text and 'illustration' in text:
        chapter=p['book']['chapters'][0]; m=re.search(r'(chapitre|section)\s+(\d+)',text)
        if m:
            idx=int(m.group(2))-1
            if not 0<=idx<len(p['book']['chapters']): raise HTTPException(400,'Section introuvable.')
            chapter=p['book']['chapters'][idx]
        b=next((x for x in chapter['blocks'] if x['kind']=='paragraph'),chapter['blocks'][0] if chapter['blocks'] else None)
        if not b: raise HTTPException(400,'La section ne contient pas de texte.')
        snapshot(p); p['book']=json.loads(json.dumps(p['book'])); p['book']['suggestions'].append({'id':uuid.uuid4().hex[:12],'chapter_id':chapter['id'],'block_id':b['id'],'page':b.get('page',1),'section':chapter['title'],'passage':b['text'][:650],'idea':'Illustration du passage sélectionné','prompt':f'{p["book"]["settings"]["image_style"]} illustration of: {b["text"][:650]}. No text.','style':p['book']['settings']['image_style'],'asset':None,'width_pct':85,'position':'after','origin':None}); p['revision']+=1; save(p,u)
        return {'message':'Une suggestion contextuelle a été ajoutée. Importez une image ou lancez une génération dans Illustrations.'}
    raise HTTPException(400,'Commande non prise en charge par l’assistant local à règles. Essayez « Corrige les problèmes de mise en page », « Ajoute une illustration au chapitre 2 » ou « Mets les illustrations en style 3D ».')

@app.get('/')
def index(): return FileResponse(ROOT/'static/index.html')
