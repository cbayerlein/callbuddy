"""Single-installation persistence, ordered events and private credential files."""
import hashlib, json, os, secrets, time
from pathlib import Path
from sqlalchemy import create_engine, String, JSON, Integer, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

class Base(DeclarativeBase): pass
class Record(Base):
    __tablename__="records"
    id: Mapped[str]=mapped_column(String,primary_key=True)
    kind: Mapped[str]=mapped_column(String,index=True)
    data: Mapped[dict]=mapped_column(JSON)
class Event(Base):
    __tablename__="events"
    seq: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    call_id: Mapped[str]=mapped_column(String,index=True)
    data: Mapped[dict]=mapped_column(JSON)

class Store:
    def __init__(self, root: Path, credential_root: Path):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.credentials=Path(credential_root);self.credentials.mkdir(parents=True,exist_ok=True)
        self.engine=create_engine(f"sqlite:///{self.root/'app.sqlite3'}",connect_args={"timeout":30})
        from .migration import upgrade
        upgrade(self.engine)
    def get(self,id):
        with Session(self.engine) as s:
            r=s.get(Record,id)
            return dict(r.data) if r else None
    def put(self,id,kind,data):
        with Session(self.engine) as s,s.begin():
            r=s.get(Record,id)
            if r:r.data=dict(data)
            else:s.add(Record(id=id,kind=kind,data=dict(data)))
        return data
    def add(self,kind,data):
        id=secrets.token_hex(12);self.put(id,kind,{**data,"id":id});return self.get(id)
    def list(self,kind):
        with Session(self.engine) as s:
            return [dict(r.data) for r in s.scalars(select(Record).where(Record.kind==kind))]
    def delete(self,id):
        with Session(self.engine) as s,s.begin():
            r=s.get(Record,id)
            if r:s.delete(r)
    def event(self,id,kind,**data):
        with Session(self.engine) as s,s.begin():
            e=Event(call_id=id,data={"kind":kind,"time":time.time(),**data});s.add(e);s.flush();seq=e.seq
        return seq
    def events(self,id,after=0):
        with Session(self.engine) as s:
            return [{"seq":e.seq,**e.data} for e in s.scalars(select(Event).where(Event.call_id==id,Event.seq>after).order_by(Event.seq).limit(250))]
    def secret(self,value=None,ref=None):
        if value is None:
            if not ref or not ref.isalnum():raise ValueError("Invalid credential reference")
            return json.loads((self.credentials/f"call-assistant-{ref}.json").read_text())["value"]
        ref=ref or secrets.token_hex(16);path=self.credentials/f"call-assistant-{ref}.json"
        with open(path,"w",opener=lambda p,f:os.open(p,f,0o600)) as f:json.dump({"value":value},f)
        os.chmod(path,0o600);return ref
    @staticmethod
    def public(data):
        return {k:v for k,v in data.items() if k not in {"credential_ref","password","api_key"}}
    def set_password(self,password):
        salt=secrets.token_hex(16)
        self.put("auth","system",{"salt":salt,"hash":hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()})
    def login(self,password):
        a=self.get("auth")
        if not a or not secrets.compare_digest(a["hash"],hashlib.scrypt(password.encode(),salt=a["salt"].encode(),n=16384,r=8,p=1).hex()):return None
        token=secrets.token_urlsafe(32)
        self.put("session:"+hashlib.sha256(token.encode()).hexdigest(),"session",{"expires":time.time()+86400})
        return token
    def authorized(self,token):
        if not token:return False
        s=self.get("session:"+hashlib.sha256(token.encode()).hexdigest())
        return bool(s and s["expires"]>time.time())

