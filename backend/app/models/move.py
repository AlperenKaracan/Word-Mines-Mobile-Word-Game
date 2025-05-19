from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class MoveRequest(BaseModel):
    move_type: str = Field(..., description="Hamle türü: 'place_word', 'shift_letter'")
    positions: Optional[List[List[int]]] = Field(None, description="Yerleştirilen veya kaydırılan harflerin pozisyonları [[row, col], ...]")
    used_letters: Optional[List[str]] = Field(None, description="Yerleştirilen harfler (JOKER dahil)")
    pass_move: Optional[bool] = Field(False, description="Pas geçilip geçilmediği")
    joker_assignments: Optional[Dict[str, str]] = Field(default_factory=dict, description="Kelime yerleştirmede jokerlerin koordinata ('row,col') göre atandığı harfler. Örn: {'7,7': 'E'}")

class MovePreviewRequest(BaseModel):
    positions: List[List[int]] = Field(..., description="Yerleştirilecek harflerin pozisyonları [[row, col], ...]")
    used_letters: List[str] = Field(..., description="Yerleştirilecek harfler (JOKER dahil)")
    joker_assignments: Optional[Dict[str, str]] = Field(default_factory=dict, description="Jokerlerin koordinata ('row,col') göre atandığı harfler. Örn: {'7,7': 'E'}")

class MovePreviewResponse(BaseModel):
    is_valid: bool = Field(..., description="Yerleştirmenin geçerli olup olmadığı.")
    potential_score: int = Field(0, description="Geçerli ise hesaplanan potansiyel skor.")
    message: str = Field("", description="Geçersiz ise veya ek bilgi için mesaj.")
    invalid_words: List[str] = Field(default_factory=list, description="Geçersiz yerleştirmede bulunan geçersiz kelimeler.")