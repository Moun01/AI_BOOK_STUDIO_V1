"""Independent PDF, structure, prompts, layout, cover, QA and export engines."""
import io, re, uuid, json, html, zipfile, base64
from pathlib import Path
from collections import Counter
import fitz
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, KeepTogether

for name, file in [('StudioSerif','DejaVuSerif.ttf'),('StudioSerifBold','DejaVuSerif-Bold.ttf'),('StudioSans','DejaVuSans.ttf'),('StudioSansBold','DejaVuSans-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path(__file__).resolve().parent.parent/'assets/fonts'/file)))
pdfmetrics.registerFontFamily('StudioSerif', normal='StudioSerif', bold='StudioSerifBold', italic='StudioSerif', boldItalic='StudioSerifBold')
pdfmetrics.registerFontFamily('StudioSans', normal='StudioSans', bold='StudioSansBold', italic='StudioSans', boldItalic='StudioSansBold')

STYLES=['photoréaliste','éditorial','cinématique','3D','aquarelle','cartoon','minimaliste','business','éducatif','luxe']

def extract_pdf(path, folder):
    doc=fitz.open(path)
    if doc.needs_pass: raise ValueError('PDF protégé par mot de passe : veuillez fournir une version déverrouillée.')
    if len(doc)>250: raise ValueError('Maximum 250 pages pour cette installation.')
    meta=doc.metadata or {}; blocks=[]; sizes=[]; tables=0; images=[]
    for n,page in enumerate(doc):
        for b in page.get_text('dict')['blocks']:
            if b['type']!=0: continue
            lines=[]; ss=[]; bold=False
            for line in b['lines']:
                lines.append(''.join(s['text'] for s in line['spans']))
                for s in line['spans']:
                    if s['text'].strip(): ss.append(s['size']); sizes.extend([round(s['size'],1)]*max(1,len(s['text'])//10)); bold |= bool(s['flags'] & 16)
            text='\n'.join(lines).strip()
            if text: blocks.append({'id':uuid.uuid4().hex[:12],'text':text,'page':n+1,'size':round(max(ss or [11]),1),'bold':bold,'bbox':list(b['bbox'])})
        try: tables+=len(page.find_tables().tables)
        except Exception: pass
        for item in page.get_images(full=True):
            if len(images)>=40: break
            try:
                raw=doc.extract_image(item[0]); asset=uuid.uuid4().hex+'.png'
                im=PILImage.open(io.BytesIO(raw['image'])); im.convert('RGB').save(folder/asset)
                images.append({'asset':asset,'page':n+1,'width':im.width,'height':im.height})
            except Exception: pass
    # Some producers emit one text block per line. Rejoin adjacent lines using
    # geometry, preserving every extracted character and the original line breaks.
    joined=[]
    for b in blocks:
        prev=joined[-1] if joined else None
        if prev and prev['page']==b['page'] and abs(prev['size']-b['size'])<.5 and prev['bold']==b['bold'] and abs(prev['bbox'][0]-b['bbox'][0])<18 and 0<=b['bbox'][1]-prev['bbox'][3]<=b['size']*.95:
            prev['text']+='\n'+b['text']; prev['bbox']=[min(prev['bbox'][0],b['bbox'][0]),prev['bbox'][1],max(prev['bbox'][2],b['bbox'][2]),b['bbox'][3]]
        else: joined.append(dict(b))
    blocks=joined
    text='\n\n'.join(b['text'] for b in blocks)
    if len(text.strip())<40: raise ValueError('Ce PDF ne contient pas assez de texte extractible. OCR requis : cette version ne traite pas les PDF scannés.')
    body=Counter(sizes).most_common(1)[0][0] if sizes else 11
    fr=len(re.findall(r'\b(le|la|les|des|une|dans|pour|et|du|est)\b',text.lower()))
    en=len(re.findall(r'\b(the|and|of|for|with|this|is|are|in)\b',text.lower()))
    return {'filename':path.name,'bytes':path.stat().st_size,'pages':len(doc),'language':'Français' if fr>en and fr>3 else 'Anglais' if en>3 else 'Indéterminée','metadata':meta,'blocks':blocks,'body_size':body,'tables':tables,'source_images':images,'text':text}

def analyze_document(raw):
    blocks=raw['blocks']; title=raw['metadata'].get('title','').strip()
    if not title or title.lower() in ('untitled','sans titre'): title=next((b['text'].replace('\n',' ') for b in blocks[:12] if b['size']>raw['body_size']+3),blocks[0]['text'].split('\n')[0])[:180]
    author=raw['metadata'].get('author','').strip()
    chapters=[]; current=None
    for b in blocks:
        t=b['text']; heading=len(t)<180 and (b['size']>raw['body_size']+2 or re.match(r'^(chapitre|chapter|introduction|conclusion|partie)\b',t,re.I))
        if heading and t.replace('\n',' ').strip()==title.strip(): kind='title'
        elif heading: kind='heading'
        elif t.startswith(('«','“','"')): kind='quote'
        else: kind='paragraph'
        if kind=='heading' or current is None:
            current={'id':uuid.uuid4().hex[:12],'title':t.replace('\n',' ') if kind=='heading' else 'Ouverture','blocks':[]}; chapters.append(current)
        current['blocks'].append({**b,'kind':kind})
    words=[w for w in re.findall(r'\b[\wÀ-ÿ]{5,}\b',raw['text'].lower()) if w not in {'cette','comme','leurs','votre','notre','entre','ainsi','chaque','faire','aussi','avoir','livre','chapitre','elles','cette','peuvent','avant','après','pour','avec','dans'}]
    keywords=[w for w,n in Counter(words).most_common(7)]
    return {'title':title,'subtitle':'','author':author,'author_bio':'','summary':raw['text'][:750], 'summary_method':'Extrait du texte original, à éditer (pas un résumé IA).','chapters':chapters,'keywords':keywords,'audience':'À préciser par l’auteur','analysis_method':'Analyse locale heuristique — titres par typographie, langue estimée, texte non réécrit.','settings':{'format':'A5','width':148,'height':210,'margin':18,'font':'StudioSerif','font_size':10.5,'accent':'#575047','layout':'Premium','image_style':'éditorial','paper':0.1,'bleed':3},'suggestions':[], 'cover_asset':None}

def build_prompts(book):
    result=[]
    for ch in book['chapters']:
        passage=next((b for b in ch['blocks'] if b['kind']=='paragraph' and len(b['text'])>100),None)
        if not passage: continue
        excerpt=passage['text'][:650]
        result.append({'id':uuid.uuid4().hex[:12],'chapter_id':ch['id'],'block_id':passage['id'],'page':passage['page'],'section':ch['title'],'passage':excerpt,'idea':f'Illustrer les éléments concrets du passage de « {ch["title"]} ».','prompt':f'Book illustration. Style: {book["settings"]["image_style"]}. Subject: {book["title"]}. Section: {ch["title"]}. Illustrate this exact passage: {excerpt}. Coherent muted palette, refined composition, no text or lettering. Do not invent recurring character identities.','style':book['settings']['image_style'],'asset':None,'width_pct':85,'position':'after','origin':None})
    return result[:30]

def page_size(s):
    return {'A4':(210*mm,297*mm),'A5':(148*mm,210*mm),'6 × 9':(6*inch,9*inch)}.get(s['format'],(float(s['width'])*mm,float(s['height'])*mm))

def safe(t): return html.escape(t).replace('\n','<br/>')

def render_interior(book, folder):
    s=book['settings']; w,h=page_size(s); m=float(s['margin'])*mm; font=s['font']; fs=float(s['font_size']); accent=HexColor(s['accent'])
    # Distinct typographic presets, still allowing explicit font/margin overrides.
    leading,heading_scale,paragraph_gap,heading_gap,align,rule={
      'Premium':(1.55,1.95,.85,19,TA_JUSTIFY,False),
      'Professionnel':(1.45,1.65,.75,16,TA_JUSTIFY,True),
      'Moderne':(1.5,2.15,1.0,23,0,True),
      'Minimaliste':(1.6,1.6,1.0,16,0,False),
      'Business':(1.4,1.75,.7,15,0,True),
      'Éducatif':(1.7,1.85,1.1,22,0,False),
      'Magazine':(1.4,2.2,.65,17,TA_JUSTIFY,True),
      'Luxe':(1.8,2.4,1.15,28,TA_JUSTIFY,False)
    }.get(s['layout'],(1.55,1.95,.85,19,TA_JUSTIFY,False))
    styles={
      'paragraph':ParagraphStyle('body',fontName=font,fontSize=fs,leading=fs*leading,spaceAfter=fs*paragraph_gap,alignment=align,allowWidows=0,allowOrphans=0,splitLongWords=1),
      'heading':ParagraphStyle('heading',fontName=font+'Bold',fontSize=fs*heading_scale,leading=fs*(heading_scale+.45),spaceBefore=12,spaceAfter=heading_gap,keepWithNext=True,textColor=accent),
      'title':ParagraphStyle('title',fontName=font+'Bold',fontSize=fs*2.6,leading=fs*3.1,spaceAfter=22,keepWithNext=True,textColor=accent),
      'quote':ParagraphStyle('quote',fontName=font,fontSize=fs+1,leading=fs*1.6,leftIndent=12,rightIndent=12,spaceBefore=10,spaceAfter=15,textColor=accent),
      'caption':ParagraphStyle('caption',fontName='StudioSans',fontSize=8,leading=11,spaceAfter=14,textColor=HexColor('#666666'))}
    story=[]
    def illustration(item):
        path=folder/item['asset']
        if not path.is_file(): return []
        iw,ih=PILImage.open(path).size; maxw=(w-2*m-12)*float(item.get('width_pct',85))/100; maxh=(h-2*m)*.48; ratio=min(maxw/iw,maxh/ih)
        im=Image(str(path),width=iw*ratio,height=ih*ratio)
        return [Spacer(1,8),im,Spacer(1,6),Paragraph(safe(item.get('caption','')),styles['caption'])]
    for ci,ch in enumerate(book['chapters']):
        if ci and s['layout'] not in ['Magazine','Minimaliste']: story.append(PageBreak())
        if not ch['blocks']: story.append(Paragraph(safe(ch['title']),styles['heading'])); story.append(Spacer(1,24))
        for b in ch['blocks']:
            items=[i for i in book['suggestions'] if i.get('asset') and i['block_id']==b['id']]
            for i in items:
                if i.get('position')=='before': story.extend(illustration(i))
            # Break very long blocks at line boundaries; ReportLab handles safe page splitting.
            story.append(Paragraph(safe(' '.join(b['text'].splitlines())),styles.get(b['kind'],styles['paragraph'])))
            for i in items:
                if i.get('position')!='before': story.extend(illustration(i))
    if not story: story=[Paragraph(' ',styles['paragraph'])]
    def page(c,doc):
        c.saveState(); c.setFont('StudioSans',7); c.setFillColor(HexColor('#79756f'))
        label=book['title'][:65]
        while pdfmetrics.stringWidth(label,'StudioSans',7)>w-2*m: label=label[:-2]+'…'
        c.drawString(m,h-m*.60,label); c.drawCentredString(w/2,m*.50,str(doc.page))
        if rule:
            c.setStrokeColor(accent); c.setLineWidth(.35); c.line(m,h-m*.77,w-m,h-m*.77)
        c.restoreState()
    doc=SimpleDocTemplate(str(folder/'interior.pdf'),pagesize=(w,h),rightMargin=m,leftMargin=m,topMargin=m,bottomMargin=m,title=book['title'],author=book['author'])
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return len(fitz.open(folder/'interior.pdf'))

def cover_panel(c,book,x,y,w,h,front=True,folder=None):
    s=book['settings']; accent=HexColor(s['accent']); c.setFillColor(accent); c.rect(x,y,w,h,fill=1,stroke=0)
    c.saveState(); c.translate(x,y)
    c.setStrokeColor(white); c.setLineWidth(.4)
    for n in range(8): c.circle(w*.93,h*.30,(n+1)*w*.14,stroke=1,fill=0)
    margin=min(18*mm,w*.14); usable=w-2*margin
    def fitted(text,top,maxheight,size,font='StudioSerif'):
        if not text: return 0
        for attempt in range(60):
            st=ParagraphStyle('coverfit',fontName=font,fontSize=size,leading=size*1.35,textColor=white,splitLongWords=1)
            p=Paragraph(safe(text),st); _,ph=p.wrap(usable,maxheight)
            if ph<=maxheight:
                p.drawOn(c,margin,top-ph); return ph
            size*=.95
            if size<6: raise ValueError('Le texte de couverture est trop long pour ce format. Réduisez-le ou choisissez un format plus grand.')
        raise ValueError('Texte de couverture trop long.')
    if front:
        if book.get('cover_asset') and folder:
            im=PILImage.open(folder/book['cover_asset']); iw,ih=im.size; ratio=min(usable/iw,h*.27/ih)
            c.drawImage(str(folder/book['cover_asset']),(w-iw*ratio)/2,h*.13,width=iw*ratio,height=ih*ratio,mask='auto')
        fitted('AI BOOK STUDIO  /  ÉDITION',h*.88,h*.035,7,'StudioSans')
        ph=fitted(book['title'],h*.79,h*.25,min(30,w/15))
        fitted(book.get('subtitle',''),h*.79-ph-5*mm,h*.09,10,'StudioSans')
        fitted(book.get('author',''),h*.105,h*.055,10,'StudioSans')
    else:
        fitted(book['summary'],h*.85,h*.51,10)
        fitted(book.get('author_bio',''),h*.265,h*.16,8,'StudioSans')
    c.restoreState()

def render_covers(book,folder,n):
    s=book['settings']; w,h=page_size(s); bleed=float(s['bleed'])*mm; spine=n/2*float(s['paper'])*mm
    # Flat spread, back | spine | front. Bleed extends the solid background.
    c=canvas.Canvas(str(folder/'cover.pdf'),pagesize=(2*w+spine+2*bleed,h+2*bleed)); c.setTitle(book['title']+' — couverture à plat')
    c.setFillColor(HexColor(s['accent'])); c.rect(0,0,2*w+spine+2*bleed,h+2*bleed,fill=1,stroke=0)
    cover_panel(c,book,bleed,bleed,w,h,False,folder); cover_panel(c,book,bleed+w+spine,bleed,w,h,True,folder)
    if spine>=5*mm:
        c.saveState(); c.translate(bleed+w+spine/2,bleed+h/2); c.rotate(90); c.setFont('StudioSans',min(9,spine*.6)); c.setFillColor(white); c.drawCentredString(0,0,(book['title']+' • '+book['author'])[:95]); c.restoreState()
    c.showPage(); c.save()
    c=canvas.Canvas(str(folder/'panels.pdf'),pagesize=(w,h))
    for front in [True,False]: cover_panel(c,book,0,0,w,h,front,folder); c.showPage()
    c.save()
    d=fitz.open(folder/'cover.pdf'); p=d[0]; p.set_trimbox(fitz.Rect(bleed,bleed,p.rect.width-bleed,p.rect.height-bleed)); p.set_bleedbox(p.mediabox); d.save(folder/'cover-boxes.pdf'); d.close(); (folder/'cover-boxes.pdf').replace(folder/'cover.pdf')
    return round(spine/mm,2)

def quality_check(book,folder,n):
    checks=[]; d=fitz.open(folder/'interior.pdf'); s=book['settings']; w,h=page_size(s); m=float(s['margin'])*mm
    outside=[]; blank=[]; sparse=[]
    for i,p in enumerate(d):
        blocks=p.get_text('blocks'); body=[b for b in blocks if b[1]>m*.7 and b[3]<h-m*.7]
        if not body and not p.get_images(): blank.append(i+1)
        if len(p.get_text().strip())<140: sparse.append(i+1)
        for b in blocks:
            if b[0]<m-2 or b[2]>w-m+2 or b[1]<0 or b[3]>h: outside.append(i+1)
    def add(code,status,text): checks.append({'code':code,'status':status,'text':text})
    add('bounds','warning' if outside else 'ok',f'Texte hors marges : pages {sorted(set(outside))}' if outside else 'Aucun débordement de texte détecté dans le PDF rendu.')
    add('blank','warning' if blank else 'ok',f'Pages sans contenu détectées : {blank}' if blank else 'Aucune page intérieure vide détectée.')
    if sparse: add('sparse','warning',f'Pages peu remplies à vérifier : {sparse}. Les ouvertures de chapitres peuvent être intentionnelles.')
    low=[]
    for item in book['suggestions']:
        if not item.get('asset'): continue
        im=PILImage.open(folder/item['asset']); display=min((w-2*m-12)*item.get('width_pct',85)/100, (h-2*m)*.48*im.width/im.height)
        dpi=round(im.width/(display/72))
        if dpi<300: low.append(f'{item["section"]} ({dpi} ppp)')
    if book.get('cover_asset'):
        im=PILImage.open(folder/book['cover_asset']); display=min(w-36*mm,h*.36*im.width/im.height); dpi=round(im.width/(display/72))
        if dpi<300: low.append(f'Couverture ({dpi} ppp)')
    add('resolution','warning' if low else 'ok','Images sous 300 ppp : '+', '.join(low) if low else 'Images intégrées : aucune résolution sous 300 ppp détectée (ou aucune image).')
    add('pagination','ok',f'{n} pages intérieures, pagination calculée au rendu.')
    add('bleed','ok',f'Couverture : fond perdu {s["bleed"]} mm ; intérieur sans éléments à bord perdu.')
    add('print','warning','PDF RVB avec polices incorporées, non certifié PDF/X. Profil colorimétrique et dos à valider auprès de l’imprimeur.')
    if n%2: add('parity','warning','Nombre de pages impair : l’imprimeur peut exiger une page blanche supplémentaire.')
    if n/2*float(s['paper'])<5: add('spine','warning','Dos inférieur à 5 mm : texte du dos omis pour rester lisible.')
    add('manual','info','Inspection visuelle nécessaire : tableaux, ordre de lecture, glyphes, chevauchements complexes et coupures sémantiques ne sont pas certifiés automatiquement.')
    return checks

def export_book(book,folder):
    n=render_interior(book,folder); spine=render_covers(book,folder,n)
    combined=fitz.open(); panels=fitz.open(folder/'panels.pdf'); inner=fitz.open(folder/'interior.pdf')
    combined.insert_pdf(panels,from_page=0,to_page=0); combined.insert_pdf(inner); combined.insert_pdf(panels,from_page=1,to_page=1); combined.set_metadata({'title':book['title'],'author':book['author']}); combined.save(folder/'complete.pdf')
    for i,page in enumerate(combined): page.get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False).save(folder/f'preview-{i}.png')
    panels[0].get_pixmap(matrix=fitz.Matrix(.65,.65),alpha=False).save(folder/'thumb.png')
    epub(book,folder)
    return {'pages':n,'preview_pages':len(combined),'spine_mm':spine,'quality':quality_check(book,folder,n)}

def epub(book,folder):
    with zipfile.ZipFile(folder/'book.epub','w') as z:
        z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml','<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        manifest=[]; spine=[]; nav=[]
        for i,ch in enumerate(book['chapters']):
            name=f'ch{i}.xhtml'; manifest.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>'); spine.append(f'<itemref idref="c{i}"/>'); nav.append(f'<li><a href="{name}">{html.escape(ch["title"])}</a></li>')
            body=''.join(f'<{"h2" if b["kind"] in ("heading","title") else "p"}>{html.escape(b["text"])}</{"h2" if b["kind"] in ("heading","title") else "p"}>' for b in ch['blocks'])
            z.writestr('OEBPS/'+name,f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>{html.escape(ch["title"])}</title></head><body>{body}</body></html>')
        z.writestr('OEBPS/nav.xhtml','<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Sommaire</title></head><body><nav epub:type="toc"><ol>'+''.join(nav)+'</ol></nav></body></html>')
        z.writestr('OEBPS/content.opf',f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">urn:uuid:{uuid.uuid4()}</dc:identifier><dc:title>{html.escape(book["title"])}</dc:title><dc:creator>{html.escape(book["author"])}</dc:creator><dc:language>{"fr" if book.get("language")=="Français" else "en" if book.get("language")=="Anglais" else "und"}</dc:language><meta property="dcterms:modified">2026-09-29T00:00:00Z</meta></metadata><manifest>'+''.join(manifest)+'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest><spine>'+''.join(spine)+'</spine></package>')

def create_demo(path):
    c=canvas.Canvas(str(path),pagesize=(148*mm,210*mm)); c.setTitle('Entreprendre autrement'); c.setAuthor('Aïcha Mensah')
    chapters=[('Entreprendre autrement','Un guide pour les entrepreneurs africains\nAïcha Mensah'),('Introduction','À Cotonou, une nouvelle génération transforme les besoins du quotidien en entreprises durables. Ce livre propose une méthode simple : observer, expérimenter puis grandir. Il s’adresse aux personnes qui souhaitent lancer une activité utile à leur communauté.\n\nEntreprendre ne commence pas par un grand bureau. Cela commence par une conversation et un problème concret à résoudre.'),('Chapitre 1 — Une idée ancrée dans le réel','Sur un marché de Cotonou, Amina observe les vendeuses de fruits. À midi, la chaleur abîme une partie de leur récolte. Elle imagine des casiers réfrigérés alimentés par des panneaux solaires, partagés par plusieurs commerçantes.\n\nAvant de construire, elle interroge vingt vendeuses. Combien perdent-elles chaque semaine ? Quel prix pourraient-elles payer ? Les réponses deviennent les premières lignes de son modèle économique.\n\n« Le meilleur point de départ est un besoin que l’on comprend vraiment. »\n\nPour valider votre idée, notez trois hypothèses et testez-les pendant une semaine. Une observation honnête vaut mieux qu’un long plan construit sur des suppositions.'),('Chapitre 2 — Construire ensemble','Dans un petit atelier de quartier, Amina travaille avec un technicien solaire et une coopérative de commerçantes. Ensemble, ils assemblent un prototype de casier. Les premières utilisatrices donnent leur avis : la serrure doit être plus simple et les compartiments plus grands.\n\nUn partenariat solide repose sur des engagements précis. Qui entretient le matériel ? Qui collecte les paiements ? Qui répond en cas de panne ? Écrire les réponses évite de nombreux conflits.\n\nL’équipe tient un carnet partagé. Chaque semaine, elle mesure le nombre de clientes, le coût de l’énergie et les fruits préservés. Ces données guident les décisions plutôt que les intuitions.'),('Chapitre 3 — Grandir sans se perdre','Six mois plus tard, deux nouveaux marchés souhaitent accueillir les casiers. Amina choisit de former une responsable locale sur chaque site. Elle privilégie la qualité du service avant la vitesse de développement.\n\nLa croissance exige de protéger la trésorerie. Séparez les finances personnelles de celles de l’activité. Gardez une réserve pour les réparations et suivez les encaissements réels.\n\nLa réussite ne se mesure pas seulement au chiffre d’affaires. Elle se voit aussi dans les pertes évitées, les emplois créés et la confiance des commerçantes.'),('Conclusion','Une entreprise durable se construit pas à pas. Écoutez les besoins, testez une solution modeste et apprenez avec vos premiers clients. Le contexte local n’est pas une contrainte à contourner : il est une source d’idées et de valeur.\n\nVotre prochain geste peut être simple : rencontrer une personne concernée par le problème que vous voulez résoudre et lui poser les bonnes questions.')]
    for title,text in chapters:
        c.setFillColor(HexColor('#3d5747')); c.setFont('StudioSerifBold',20)
        p=Paragraph(safe(title),ParagraphStyle('h',fontName='StudioSerifBold',fontSize=20,leading=25,textColor=HexColor('#3d5747'))); _,ph=p.wrap(112*mm,100); p.drawOn(c,18*mm,180*mm-ph)
        p=Paragraph(safe(text),ParagraphStyle('b',fontName='StudioSerif',fontSize=10.5,leading=17)); _,bh=p.wrap(112*mm,400); p.drawOn(c,18*mm,170*mm-ph-bh); c.showPage()
    c.save()
