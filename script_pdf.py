"""Independent PDF pages, preserving pypdf extraction and page order."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import multiprocessing
import os

_reader=None

def initialize_reader(path):
    global _reader
    from pypdf import PdfReader
    _reader=PdfReader(path)

def extract_page(index):
    return index,(_reader.pages[index].extract_text() or '').strip()

def extract_pdf(path, progress):
    from pypdf import PdfReader
    pages=PdfReader(str(path)).pages;count=len(pages)
    if count<50:
        result=[]
        for index,page in enumerate(pages):
            progress('Extrayendo PDF',index,count);result.append((page.extract_text() or '').strip())
    else:
        result=['']*count;completed=0
        # The parser is Python CPU work: separate processes avoid GIL contention with Qt.
        workers=min(4,max(1,(os.cpu_count() or 2)-1))
        executor=ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize_reader,initargs=(str(path),))
        pending=set();next_page=0
        try:
            while next_page<count and len(pending)<workers*2:
                pending.add(executor.submit(extract_page,next_page));next_page+=1
            while pending:
                progress('Extrayendo PDF',completed,count)
                done,pending=wait(pending,timeout=0.1,return_when=FIRST_COMPLETED)
                for future in done:
                    index,text=future.result();result[index]=text;completed+=1
                    if next_page<count:
                        pending.add(executor.submit(extract_page,next_page));next_page+=1
        finally:
            for future in pending:future.cancel()
            executor.shutdown(wait=True,cancel_futures=True)
    progress('Extrayendo PDF',count,count)
    text='\n\n'.join(result).strip()
    if not text:raise ValueError('El PDF no contiene texto seleccionable. Si es escaneado, necesita OCR.')
    return text
