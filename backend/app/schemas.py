from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Operation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['replace_text','text','image','delete_image','replace_image','transform_image','annotation','delete_pages','reorder','rotate','duplicate','blank','insert','crop','watermark','numbers','metadata','compress']
    page_id: str | None = None
    page_ids: list[str] = Field(default_factory=list)
    rect: tuple[float,float,float,float] | None = None
    source_rect: tuple[float,float,float,float] | None = None
    text: str = Field(default='', max_length=100000)
    original: str | None = None
    font: Literal['helv','tiro','cour'] = 'helv'
    font_size: float = Field(default=12, ge=4, le=300)
    color: str = '#172033'
    behind: bool = False
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: Literal['left','center','right'] = 'left'
    opacity: float = Field(default=1, ge=0, le=1)
    angle: int = 90
    xref: int | None = None
    asset_id: str | None = None
    source_id: str | None = None
    annotation: Literal['highlight','underline','strikeout','text','rect','circle','line','arrow','ink','stamp'] = 'rect'
    points: list[tuple[float,float]] = Field(default_factory=list, max_length=20000)
    metadata: dict[str,str] = Field(default_factory=dict)

class Mutation(BaseModel):
    revision: int
    operation: Operation

class HistoryRequest(BaseModel):
    revision: int
    direction: Literal['undo','redo']

class ExportRequest(BaseModel):
    page_ids: list[str] | None = None
    password: str = Field(default='', max_length=128)

class JobRequest(BaseModel):
    kind: Literal['ocr','docx','word_pdf']
    language: Literal['eng','ara','eng+ara'] = 'eng'
    mode: Literal['editable','layout'] = 'editable'
