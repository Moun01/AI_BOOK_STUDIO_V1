"""Real optional providers. No stock image or procedural drawing masquerades as AI."""
import base64, io, uuid
import requests
from PIL import Image

class ProviderUnavailable(ValueError): pass

class LocalImageProvider:
    def generate(self,prompt,settings,folder):
        if settings.get('image_provider','none')=='none':
            raise ProviderUnavailable('Aucun modèle d’image connecté. Importez une image gratuitement ou connectez Stable Diffusion (AUTOMATIC1111 --api) dans Paramètres → IA. Aucun générateur IA n’est installé sur ce serveur.')
        if settings.get('image_provider')=='a1111':
            try:
                r=requests.post('http://127.0.0.1:7860/sdapi/v1/txt2img',json={'prompt':prompt,'negative_prompt':'text, watermark, distorted anatomy','steps':20,'width':768,'height':768,'seed':-1},timeout=240); r.raise_for_status(); raw=base64.b64decode(r.json()['images'][0].split(',')[-1])
            except requests.RequestException as e: raise ProviderUnavailable('Stable Diffusion local indisponible sur le port 7860. Installez un modèle et lancez AUTOMATIC1111 avec --api. '+str(e)[:180])
        elif settings.get('image_provider')=='openai':
            if not settings.get('image_key'): raise ProviderUnavailable('API externe nécessaire : clé Image AI manquante. Cette option peut être payante.')
            r=requests.post('https://api.openai.com/v1/images/generations',headers={'Authorization':'Bearer '+settings['image_key']},json={'model':'gpt-image-1','prompt':prompt,'size':'1024x1024','n':1},timeout=240)
            if not r.ok: raise ProviderUnavailable(f'Le fournisseur externe a refusé la génération (HTTP {r.status_code}). Vérifiez votre clé et votre quota.')
            raw=base64.b64decode(r.json()['data'][0]['b64_json'])
        else: raise ProviderUnavailable('Fournisseur inconnu.')
        im=Image.open(io.BytesIO(raw)); im.verify(); im=Image.open(io.BytesIO(raw)).convert('RGB'); name=uuid.uuid4().hex+'.png'; im.save(folder/name); return name

class TextProvider:
    def analyze(self,book,settings):
        text='\n\n'.join(b['text'] for c in book['chapters'] for b in c['blocks'])[:22000]
        prompt='Analyse ce texte sans modifier le manuscrit. Réponds uniquement en JSON avec les clés summary (résumé français de 100 mots maximum), audience (public probable), keywords (liste de 7 mots). N’invente pas de biographie. Texte : '+text
        try:
            if settings.get('text_provider')=='ollama':
                r=requests.post('http://127.0.0.1:11434/api/generate',json={'model':settings.get('text_model') or 'qwen2.5:3b','prompt':prompt,'stream':False,'format':'json'},timeout=240); r.raise_for_status(); result=r.json()['response']
            elif settings.get('text_provider')=='openai':
                if not settings.get('text_key'): raise ProviderUnavailable('API externe nécessaire : clé Text AI manquante.')
                r=requests.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':'Bearer '+settings['text_key']},json={'model':settings.get('text_model') or 'gpt-4o-mini','messages':[{'role':'user','content':prompt}],'response_format':{'type':'json_object'}},timeout=180)
                if not r.ok: raise ProviderUnavailable(f'Text AI : erreur fournisseur HTTP {r.status_code}.')
                result=r.json()['choices'][0]['message']['content']
            else: raise ProviderUnavailable('Connectez Ollama gratuitement ou une API Text AI dans les paramètres. L’analyse locale reste disponible sans modèle.')
        except requests.RequestException: raise ProviderUnavailable('Le modèle de texte est inaccessible. Pour Ollama : démarrer le serveur sur le port 11434 et installer le modèle indiqué.')
        import json
        data=json.loads(result)
        return {'summary':str(data.get('summary',''))[:1300],'audience':str(data.get('audience',''))[:300],'keywords':[str(x)[:50] for x in data.get('keywords',[])[:10]]}
