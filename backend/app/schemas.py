from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "replace_text",
        "replace_scan",
        "text",
        "image",
        "delete_image",
        "replace_image",
        "transform_image",
        "annotation",
        "delete_pages",
        "reorder",
        "rotate",
        "duplicate",
        "blank",
        "insert",
        "crop",
        "watermark",
        "numbers",
        "metadata",
        "compress",
    ]
    page_id: str | None = None
    page_ids: list[str] = Field(default_factory=list)
    rect: tuple[float, float, float, float] | None = None
    source_rect: tuple[float, float, float, float] | None = None
    text: str = Field(default="", max_length=100000)
    original: str | None = None
    font: Literal["helv", "tiro", "cour"] = "helv"
    fit_text: bool = True
    background_color: str = "#ffffff"
    font_size: float = Field(default=12, ge=4, le=300)
    color: str = "#172033"
    behind: bool = False
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: Literal["left", "center", "right"] = "left"
    opacity: float = Field(default=1, ge=0, le=1)
    angle: int = 0
    signature: bool = False
    xref: int | None = None
    asset_id: str | None = None
    source_id: str | None = None
    annotation: Literal[
        "highlight",
        "underline",
        "strikeout",
        "text",
        "rect",
        "circle",
        "line",
        "arrow",
        "ink",
        "stamp",
    ] = "rect"
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=20000)
    metadata: dict[str, str] = Field(default_factory=dict)


class Mutation(BaseModel):
    revision: int
    operation: Operation


class HistoryRequest(BaseModel):
    revision: int
    direction: Literal["undo", "redo"]


class ExportRequest(BaseModel):
    page_ids: list[str] | None = None
    password: str = Field(default="", max_length=128)


class JobRequest(BaseModel):
    kind: Literal["ocr", "ocr_region", "docx", "word_pdf"]
    language: Literal["eng", "ara", "eng+ara"] = "eng"
    mode: Literal["editable", "layout"] = "editable"
    page_id: str | None = None
    rect: tuple[float, float, float, float] | None = None
    dpi: int = Field(default=300, ge=150, le=600)
    recognition_mode: Literal["auto", "line", "numbers"] = "auto"


class DiscardRequest(BaseModel):
    revision: int


class RegionExport(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    revision: int
    rect: tuple[float, float, float, float]
    dpi: int = Field(default=300, ge=72, le=600)
    remove_white: bool = False
