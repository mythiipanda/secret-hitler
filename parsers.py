from typing import Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

class NominationOut(BaseModel):
    nominated_chancellor: int = Field(..., description="Player id nominated for Chancellor")
    public_statement: Optional[str] = Field("", description="Public statement to table")
    private_thoughts: Optional[str] = Field("", description="Internal reasoning / chain-of-thought")

class VoteOut(BaseModel):
    vote: bool = Field(..., description="True for Ja, False for Nein")
    public_statement: Optional[str] = Field("", description="Optional public statement")
    private_thoughts: Optional[str] = Field("", description="Internal reasoning / chain-of-thought")

class PresidentLegislateOut(BaseModel):
    discard: Literal["liberal", "fascist"] = Field(..., description="Policy to discard")
    public_claim: Optional[str] = Field("", description="Public claim by President")
    private_thoughts: Optional[str] = Field("", description="Internal reasoning / chain-of-thought")

class ChancellorLegislateOut(BaseModel):
    enact: Literal["liberal", "fascist"] = Field(..., description="Policy to enact")
    public_claim: Optional[str] = Field("", description="Public claim by Chancellor")
    private_thoughts: Optional[str] = Field("", description="Internal reasoning / chain-of-thought")

class InvestigateOut(BaseModel):
    investigate: int = Field(..., description="Player id to investigate")
    reason: Optional[str] = Field("", description="Reasoning for investigation")
    private_thoughts: Optional[str] = Field("", description="Internal reasoning / chain-of-thought")

nom_parser = PydanticOutputParser(pydantic_object=NominationOut)
vote_parser = PydanticOutputParser(pydantic_object=VoteOut)
pres_parser = PydanticOutputParser(pydantic_object=PresidentLegislateOut)
chanc_parser = PydanticOutputParser(pydantic_object=ChancellorLegislateOut)
inv_parser = PydanticOutputParser(pydantic_object=InvestigateOut)