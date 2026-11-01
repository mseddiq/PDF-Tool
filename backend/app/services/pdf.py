import math
import uuid
import html
import io
from PIL import Image
from pathlib import Path
from fastapi import HTTPException
import pymupdf as fitz
from ..core import folder, identifier, load, current, page_ids, MAX_PAGES

def rgb(value):
    try:
        if len(value)!=7 or value[0]!='#': raise ValueError()
        return tuple(int(value[i:i+2],16)/255 for i in (1,3,5))
    except (ValueError,TypeError):
        raise HTTPException(422, 'Use a six-digit hex color.')

def rectangle(op, page):
    if op.rect is None or not all(math.isfinite(v) for v in op.rect):
        raise HTTPException(422, 'A valid object rectangle is required.')
    r=fitz.Rect(op.rect)
    bounds=page.rect * page.derotation_matrix
    if r.is_empty or r.is_infinite or not bounds.contains(r):
        raise HTTPException(422, 'Object must fit within the page boundaries.')
    return r

def index(ids, value):
    try: return ids.index(value)
    except ValueError: raise HTTPException(422, 'Page no longer exists.')

def apply(doc, ids, op, doc_id):
    ids=ids.copy()
    kind=op.kind
    if kind=='reorder':
        if len(op.page_ids)!=len(ids) or set(op.page_ids)!=set(ids):
            raise HTTPException(422,'Reorder must include every page exactly once.')
        doc.select([index(ids,p) for p in op.page_ids]); return op.page_ids
    if kind=='delete_pages':
        remove=set(op.page_ids)
        if not remove or not remove.issubset(ids) or len(remove)==len(ids):
            raise HTTPException(422,'Select pages to delete and keep at least one page.')
        keep=[p for p in ids if p not in remove]
        doc.select([index(ids,p) for p in keep]); return keep
    if kind=='blank':
        at=index(ids,op.page_id)+1 if op.page_id else len(ids)
        source=doc[max(0,at-1)]
        doc.new_page(pno=at,width=source.rect.width,height=source.rect.height)
        ids.insert(at,uuid.uuid4().hex); return ids
    if kind=='insert':
        if not op.source_id or op.source_id==doc_id:
            raise HTTPException(422,'Open a different source PDF first.')
        source_state=load(op.source_id)
        source_ids=page_ids(source_state)
        selected=op.page_ids or source_ids
        if len(ids)+len(selected)>MAX_PAGES: raise HTTPException(422,'Page limit exceeded.')
        at=index(ids,op.page_id)+1 if op.page_id else len(ids)
        with fitz.open(current(op.source_id,source_state)) as source:
            for offset,pid in enumerate(selected):
                n=index(source_ids,pid)
                doc.insert_pdf(source,from_page=n,to_page=n,start_at=at+offset)
                ids.insert(at+offset,uuid.uuid4().hex)
        return ids
    if kind=='duplicate':
        selected=op.page_ids or [op.page_id]
        for pid in selected:
            n=index(ids,pid); doc.fullcopy_page(n,to=n+1); ids.insert(n+1,uuid.uuid4().hex)
        return ids
    if kind=='rotate':
        if op.angle % 90: raise HTTPException(422,'Rotation must be a multiple of 90 degrees.')
        for pid in op.page_ids or [op.page_id]:
            p=doc[index(ids,pid)]; p.set_rotation(p.rotation+op.angle)
        return ids
    if kind in ('watermark','numbers'):
        color=rgb(op.color)
        for n,p in enumerate(doc):
            box=p.rect * p.derotation_matrix
            p.insert_text((box.x0+24,box.y1-24),op.text if kind=='watermark' else str(n+1),fontsize=op.font_size,color=color,fill_opacity=op.opacity)
        return ids
    if kind=='metadata':
        allowed={'title','author','subject','keywords','creator'}
        if not set(op.metadata).issubset(allowed): raise HTTPException(422,'Unsupported metadata field.')
        doc.set_metadata({**doc.metadata,**op.metadata}); return ids
    if kind=='compress': return ids # Every commit rewrites/deflates and collects garbage; no lossy rasterization.
    p=doc[index(ids,op.page_id)]
    if kind=='crop':
        target=rectangle(op,p)+fitz.Rect(p.cropbox_position,p.cropbox_position)
        p.set_cropbox(target); return ids
    if kind in ('delete_image','replace_image','transform_image'):
        if op.xref not in {i[0] for i in p.get_images()}:
            raise HTTPException(422,'Selected embedded image no longer exists.')
        # xref replacement affects every use of this resource; UI explicitly warns.
        if kind=='delete_image': p.delete_image(op.xref)
        elif kind=='transform_image':
            uses=sum(len(pg.get_image_rects(op.xref)) for pg in doc)
            if uses!=1: raise HTTPException(422,'This resource is shared. Insert a separate copy rather than moving every use.')
            target=rectangle(op,p)
            extracted=fitz.Pixmap(doc,op.xref)
            masks=doc.extract_image(op.xref).get('smask',0)
            if masks: extracted=fitz.Pixmap(extracted,fitz.Pixmap(doc,masks))
            data=extracted.tobytes('png')
            p.delete_image(op.xref)
            insert_image(p,target,data,op)
        else: p.replace_image(op.xref,filename=str(folder(doc_id)/('asset-'+identifier(op.asset_id or '')+'.png')))
        return ids
    r=rectangle(op,p); color=rgb(op.color)
    if kind in ('replace_text','text'):
        families={'helv':['helv','hebo','heit','hebi'],'tiro':['tiro','tibo','tiit','tibi'],'cour':['cour','cobo','coit','cobi']}
        font=families[op.font][int(op.bold)+2*int(op.italic)]
        complex_script=any(ord(c)>255 for c in op.text)
        if kind=='replace_text':
            source_rect=fitz.Rect(op.source_rect) if op.source_rect else r
            spans=[s for b in p.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans'] if fitz.Rect(s['bbox']).intersects(source_rect)]
            if op.original is None or not any(s['text']==op.original and max(abs(s['bbox'][i]-source_rect[i]) for i in range(4))<1 for s in spans):
                raise HTTPException(409,'Text span changed or selection is ambiguous. Select it again.')
            p.add_redact_annot(source_rect,fill=False)
            p.apply_redactions(images=0,graphics=0,text=0)
        # Fit first on a temporary page; an overflow aborts the whole revision.
        probe=fitz.open(); test=probe.new_page(width=p.mediabox.width,height=p.mediabox.height)
        align={'left':0,'center':1,'right':2}[op.align]
        if complex_script:
            direction='rtl' if any('\u0600'<=c<='\u06ff' for c in op.text) else 'ltr'
            content=f'<div dir="{direction}" style="font-size:{op.font_size}pt;color:{op.color};text-align:{op.align};font-weight:{"bold" if op.bold else "normal"};font-style:{"italic" if op.italic else "normal"}">{html.escape(op.text).replace(chr(10),"<br>")}</div>'
            font_dir=Path(__file__).resolve().parents[1]/'fonts'
            css='@font-face {font-family: studio; src: url(DejaVuSans.ttf);} * {font-family: studio;}'
            archive=fitz.Archive(str(font_dir))
            spare,_=test.insert_htmlbox(r,content,scale_low=1,css=css,archive=archive)
            if spare<0: raise HTTPException(422,'Text overflows its box. Enlarge the box or reduce font size.')
            p.insert_htmlbox(r,content,scale_low=1,css=css,archive=archive)
        else:
            # Extracted glyph boxes include ascender/descender metrics; preserve baseline for a single span.
            if kind=='replace_text' and '\n' not in op.text and op.align=='left':
                f=fitz.Font(fontname=font)
                if f.text_length(op.text,fontsize=op.font_size)>r.width+.5:
                    raise HTTPException(422,'Replacement is wider than the selected span. Reduce font size or use a larger text block.')
                baseline=r.y0+op.font_size*f.ascender
                p.insert_text((r.x0,baseline),op.text,fontname=font,fontsize=op.font_size,color=color)
            else:
                spare=test.insert_textbox(r,op.text,fontname=font,fontsize=op.font_size,color=color,align=align)
                if spare<0: raise HTTPException(422,'Text overflows its box. Enlarge the box or reduce font size.')
                p.insert_textbox(r,op.text,fontname=font,fontsize=op.font_size,color=color,align=align)
        probe.close()
        if op.underline:
            annot=p.add_underline_annot(r); annot.set_colors(stroke=color); annot.update()
    elif kind=='image':
        asset=folder(doc_id)/('asset-'+identifier(op.asset_id or '')+'.png')
        if not asset.exists(): raise HTTPException(404,'Image asset missing.')
        if op.angle%90: raise HTTPException(422,'Image rotation must be a multiple of 90 degrees.')
        insert_image(p,r,asset.read_bytes(),op)
    elif kind=='annotation':
        t=op.annotation
        if t=='highlight': a=p.add_highlight_annot(r)
        elif t=='underline': a=p.add_underline_annot(r)
        elif t=='strikeout': a=p.add_strikeout_annot(r)
        elif t=='text': a=p.add_text_annot(r.tl,op.text or 'Note')
        elif t=='rect': a=p.add_rect_annot(r)
        elif t=='circle': a=p.add_circle_annot(r)
        elif t in ('arrow','line'):
            a=p.add_line_annot(r.tl,r.br)
            if t=='arrow': a.set_line_ends(0,4)
        elif t=='ink':
            if len(op.points)<2 or any(not (p.rect*p.derotation_matrix).contains(fitz.Point(pt)) for pt in op.points):
                raise HTTPException(422,'Draw at least two points inside the page.')
            a=p.add_ink_annot([op.points])
        else: a=p.add_stamp_annot(r,stamp=0)
        a.set_colors(stroke=color); a.set_opacity(op.opacity); a.update()
    return ids


def insert_image(page,rect,data,op):
    if op.angle%90:raise HTTPException(422,'Image rotation must be a multiple of 90 degrees.')
    if op.opacity<1:
        with Image.open(io.BytesIO(data)) as image:
            image=image.convert('RGBA')
            image.putalpha(image.getchannel('A').point(lambda v:round(v*op.opacity)))
            stream=io.BytesIO();image.save(stream,format='PNG');data=stream.getvalue()
    page.insert_image(rect,stream=data,rotate=op.angle%360,overlay=not op.behind)
