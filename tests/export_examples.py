"""Generate a reproducible, illustrated demonstration and test each paper format."""
from pathlib import Path
import sys, shutil, json
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.engines import create_demo,extract_pdf,analyze_document,build_prompts,export_book
root=Path(__file__).resolve().parent.parent
folder=root/'examples/livre-demonstration';folder.mkdir(parents=True,exist_ok=True)
create_demo(folder/'original.pdf')
raw=extract_pdf(folder/'original.pdf',folder)
b=analyze_document(raw);b['language']=raw['language'];b['suggestions']=build_prompts(b)
b['subtitle']='Un guide pour les entrepreneurs africains'
b['settings']['accent']='#3d5747'
name='e'*32+'.png';shutil.copyfile(root/'examples/illustration-demo.png',folder/name)
x=next(x for x in b['suggestions'] if 'idée' in x['section'].lower());x['asset']=name;x['origin']='IA Arena · illustration pré-générée';x['caption']='Illustration générée avec Arena pour ce livre de démonstration.'
b['summary']='À Cotonou, Amina part d’un besoin concret : aider les vendeuses de fruits à préserver leurs récoltes. De ses premières conversations au développement de casiers réfrigérés solaires, son parcours explore trois étapes : observer le terrain, construire avec les autres et grandir sans se perdre.\n\nCe court manuscrit fictif permet de tester la composition et l’illustration d’un livre dans AI BOOK STUDIO.'
b['summary_method']='Texte de présentation rédigé pour le document de démonstration, pas généré par l’application.'
result=export_book(b,folder)
(folder/'projet.json').write_text(json.dumps(b,ensure_ascii=False,indent=2));(folder/'controle-qualite.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('Exemple illustré exporté :',result['pages'],'pages intérieures.')
# Test non-default formats and typography without polluting the deliverables.
import tempfile
with tempfile.TemporaryDirectory(dir=root/'tests') as tmp:
    tmp=Path(tmp);shutil.copyfile(folder/name,tmp/name)
    for fmt,layout in [('A4','Moderne'),('6 × 9','Magazine'),('Personnalisé','Luxe')]:
        b['settings'].update(format=fmt,width=120,height=190,layout=layout)
        r=export_book(b,tmp);assert not any(q['code']=='bounds' and q['status']=='warning' for q in r['quality']),r
        print('Format vérifié :',fmt,'/',layout,';',r['pages'],'pages')
