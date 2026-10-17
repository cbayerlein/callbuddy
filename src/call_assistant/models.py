"""Public application contracts; secret values are input-only."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, SecretStr, model_validator

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Person(Contract):
    name: str = ""
    callback: str = ""
    notes: str = ""

class Settings(Contract):
    person: Person = Field(default_factory=Person)
    theme: Literal["system", "light", "dark"] = "system"
    language: Literal["de", "en"] = "de"
    default_sip: str | None = None
    default_model: str | None = None
    default_text_model: str | None = None
    model_selection: Literal["manual", "recommended"] = "manual"
    recording: bool = False

class SipProfile(Contract):
    name: str = Field(min_length=1,max_length=100)
    username: str = Field(min_length=1,max_length=200)
    auth_id: str = ""
    domain: str = Field(min_length=1,max_length=253)
    registrar: str = Field(min_length=1,max_length=253)
    port: int = Field(default=5060, ge=1, le=65535)
    proxy: str = ""
    transport: Literal["udp", "tcp", "tls"] = "udp"
    caller_id: str = ""
    phone_number: str = Field(default="",pattern=r"^(?:\+[1-9][0-9]{6,14})?$")
    stun: str = ""
    phone_eur_per_minute: float = Field(default=0,ge=0,le=100)
    tariff_scope: Literal["any","de_standard"] = "any"
    pricing_confirmed: bool = False
    password: SecretStr | None = None
    @model_validator(mode="after")
    def hosts(self):
        for value in (self.username,self.auth_id,self.caller_id):
            if value and any(c in value for c in "\r\n <>/@\";:"):
                raise ValueError("Enter SIP user identifiers without URI syntax or whitespace")
        for value in (self.domain,self.registrar,self.proxy,self.stun):
            if value and any(c in value for c in "\r\n <>/@"):
                raise ValueError("Enter host names without URI credentials or whitespace")
        return self

class ModelProfile(Contract):
    name: str = Field(min_length=1,max_length=100)
    provider: Literal["openai","google"]
    model: str = Field(min_length=1,max_length=120,pattern=r"^[a-zA-Z0-9._/-]+$")
    prep_model: str = ""
    backend_model: str = Field(default="gpt-6-luna",min_length=1,max_length=120,pattern=r"^[a-zA-Z0-9._/-]+$")
    purpose: Literal["live","text"] = "live"
    voice: str = Field(default="marin",min_length=1,max_length=60)
    language: Literal["de","en"] = "de"
    api_key: SecretStr | None = None
    eagerness: Literal["auto","low","medium","high"] = "auto"
    maximum_token_eur_per_million: float = Field(default=100,gt=0,le=10000)
    pricing_confirmed: bool = False

class Preparation(Contract):
    number: str = Field(pattern=r"^\+[1-9][0-9]{6,14}$")
    objective: str = Field(min_length=3,max_length=2000)
    scenario: Literal["restaurant","doctor","airline","general"] = "general"
    answers: dict[str,str] = Field(default_factory=dict)
    facts: dict[str,str] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    permissions: str = ""
    model_profile: str | None = None
    sip_profile: str | None = None

class StartCall(Contract):
    request_id: str = Field(min_length=8,max_length=100)
    mode: Literal["live"] = "live"
    accepted_revision: int

class Command(Contract):
    command_id: str = Field(min_length=8,max_length=100)
    kind: Literal["pause","resume","hangup","dtmf","instruction","takeover","release"]
    text: str = Field(default="",max_length=4000)

class Answer(Contract):
    answer: str = Field(min_length=1,max_length=2000)

class Memory(Contract):
    text: str = Field(min_length=1,max_length=2000)
    category: Literal["fact","preference"] = "preference"
    source: str = "user"
    confirmed: bool = False

class TextRequest(Contract):
    model_profile: str
    request_id: str = Field(min_length=8,max_length=100)

class ResearchCandidate(Contract):
    name: str = Field(min_length=1,max_length=200)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence: list[str] = Field(min_length=1,max_length=20)
    notes: str = Field(default="",max_length=4000)
    model_profile: str | None = None
    measured_audio: bool = False
    human_listening_approved: bool = False
    role_and_reference_passed: bool = False
    eagerness: Literal["auto","low","medium","high"] = "auto"

