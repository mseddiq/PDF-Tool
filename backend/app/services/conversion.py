import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Event
import pymupdf as fitz
from docx import Document
from docx.shared import Pt
from PIL import Image
import pytesseract
from ..core import TIMEOUT

class Cancelled(Exception): pass

def checkpoint(cancel):
    if cancel.is_set(): raise Cancelled('Job cancelled.')

def word_to_pdf(source, destination, cancel):
    binary=shutil.which('libreoffice') or shutil.which('soffice')
    if not binary: raise ValueError('LibreOffice is not installed. Install it and add its program directory to PATH.')
    with tempfile.TemporaryDirectory(prefix='studio-office-') as tmp:
        profile=Path(tmp)/'profile'
        command=[binary,f'-env:UserInstallation={profile.as_uri()}','--headless','--convert-to','pdf','--outdir',tmp,str(source.resolve())]
        import time
        with subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) as proc:
            deadline=time.monotonic()+TIMEOUT
            while proc.poll() is None:
                if cancel.wait(.15) or time.monotonic()>deadline:
                    proc.kill(); proc.wait()
                    if cancel.is_set(): raise Cancelled('Job cancelled.')
                    raise ValueError('Word conversion timed out.')
            result=Path(tmp)/(source.stem+'.pdf')
            if proc.returncode or not result.exists(): raise ValueError('LibreOffice could not render this Word document.')
            with fitz.open(result) as check:
                if not len(check): raise ValueError('Word conversion produced no pages.')
            shutil.copyfile(result,destination)

def pdf_to_word(source, destination, mode, cancel, progress):
    out=Document(); warnings=['PDF-to-Word reconstruction is approximate. Review reading order, tables, fonts, and page breaks.']
    with fitz.open(source) as pdf:
        for n,page in enumerate(pdf):
            checkpoint(cancel)
            section=out.sections[0] if n==0 else out.add_section()
            section.page_width=Pt(page.rect.width); section.page_height=Pt(page.rect.height)
            section.left_margin=section.right_margin=Pt(24)
            section.top_margin=section.bottom_margin=Pt(24)
            tables=page.find_tables().tables
            table_boxes=[]
            for found in tables:
                values=found.extract()
                if not values or not values[0]:continue
                table=out.add_table(rows=len(values),cols=max(len(row) for row in values))
                table.style='Table Grid'
                for row_n,row in enumerate(values):
                    for col_n,value in enumerate(row):table.cell(row_n,col_n).text=value or ''
                table_boxes.append(fitz.Rect(found.bbox))
            blocks=page.get_text('dict',sort=True)['blocks']
            for block in blocks:
                if block['type']==1:
                    try:
                        out.add_picture(io.BytesIO(block['image']),width=Pt(min(block['width'],page.rect.width-48)))
                    except (ValueError,KeyError): warnings.append(f'Image on page {n+1} could not be reconstructed.')
                    continue
                for line in block.get('lines',[]):
                    if any(box.contains(fitz.Rect(line['bbox'])) for box in table_boxes):continue
                    para=out.add_paragraph()
                    if mode=='layout':
                        para.paragraph_format.left_indent=Pt(max(0,line['bbox'][0]-24))
                        para.paragraph_format.space_after=Pt(0)
                    for span in line['spans']:
                        run=para.add_run(span['text']); run.font.size=Pt(span['size'])
                        run.bold=bool(span['flags']&16); run.italic=bool(span['flags']&2)
                        from docx.shared import RGBColor
                        run.font.color.rgb=RGBColor.from_string(f"{span['color']:06x}")
                        if any('\u0600'<=c<='\u06ff' for c in span['text']):
                            from docx.oxml import OxmlElement
                            bidi=OxmlElement('w:bidi'); para._p.get_or_add_pPr().append(bidi)
            if not page.get_text().strip(): warnings.append(f'Page {n+1} has no native text. Run OCR before converting.')
            progress((n+1)/len(pdf))
    out.save(destination)
    return list(dict.fromkeys(warnings))

def ocr_pdf(source,destination,language,cancel,progress):
    available=set(pytesseract.get_languages(config=''))
    if not set(language.split('+')).issubset(available):
        raise ValueError(f'Missing Tesseract language pack: {language}. Install the selected packs first.')
    confidences=[]
    with fitz.open(source) as pdf, fitz.open() as result:
        for n,page in enumerate(pdf):
            checkpoint(cancel)
            if page.get_text().strip():
                result.insert_pdf(pdf,from_page=n,to_page=n)
            else:
                pix=page.get_pixmap(dpi=180,alpha=False)
                image=Image.open(io.BytesIO(pix.tobytes('png')))
                data=pytesseract.image_to_data(image,lang=language,output_type=pytesseract.Output.DICT,timeout=TIMEOUT)
                values=[float(c) for c in data['conf'] if float(c)>=0]
                confidences.append({'page':n+1,'confidence':round(sum(values)/len(values),1) if values else 0,
                                    'text':' '.join(t for t in data['text'] if t.strip())})
                checkpoint(cancel)
                layer=pytesseract.image_to_pdf_or_hocr(image,lang=language,extension='pdf',timeout=TIMEOUT)
                with fitz.open(stream=layer,filetype='pdf') as searchable:
                    target=result.new_page(width=page.rect.width,height=page.rect.height)
                    # OCR PDF contains an image and invisible text, preserving the scanned appearance.
                    target.show_pdf_page(target.rect,searchable,0)
            progress((n+1)/len(pdf))
        result.save(destination,garbage=4,deflate=True)
    return confidences
