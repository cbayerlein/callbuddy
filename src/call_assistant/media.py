"""Authenticated browser audio uses local datagrams, not persistent recordings."""
import asyncio,os,socket,time
from fractions import Fraction
from pathlib import Path
import av,numpy as np
from aiortc import RTCPeerConnection,RTCSessionDescription,MediaStreamTrack,RTCConfiguration

class MonitorTrack(MediaStreamTrack):
    kind="audio"
    def __init__(self):super().__init__();self.queue=asyncio.Queue(maxsize=100);self.pts=0;self.next=time.monotonic()
    async def recv(self):
        await asyncio.sleep(max(0,self.next-time.monotonic()));self.next=time.monotonic()+.02
        pcm=self.queue.get_nowait() if not self.queue.empty() else bytes(640)
        f=av.AudioFrame.from_ndarray(np.frombuffer(pcm,dtype=np.int16).reshape(1,-1),format="s16",layout="mono")
        f.sample_rate=16000;f.pts=self.pts;f.time_base=Fraction(1,16000);self.pts+=320;return f

async def browser_peer(runtime,id,data):
    if data.get("type")!="offer" or not isinstance(data.get("sdp"),str) or len(data["sdp"])>100000:raise ValueError("Valid WebRTC offer required")
    call=runtime.store.get(id);root=runtime.store.root/"calls"/id;root.mkdir(parents=True,exist_ok=True)
    if id in runtime.peers:await runtime.peers[id].close()
    peer=RTCPeerConnection(RTCConfiguration(iceServers=[]));runtime.peers[id]=peer;track=MonitorTrack();peer.addTrack(track)
    path=root/"monitor.sock"
    if path.exists():path.unlink()
    class Receiver(asyncio.DatagramProtocol):
        def datagram_received(self,pcm,addr):
            if len(pcm)==640 and not track.queue.full():track.queue.put_nowait(pcm)
    transport,_=await asyncio.get_running_loop().create_datagram_endpoint(Receiver,local_addr=str(path),family=socket.AF_UNIX)
    path.chmod(0o600)
    tasks=[]
    @peer.on("track")
    def incoming(audio):
        if audio.kind!="audio":return
        async def microphone():
            resampler=av.AudioResampler(format="s16",layout="mono",rate=16000)
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as s:
                while True:
                    frame=await audio.recv()
                    if not runtime.store.get(id).get("takeover"):continue
                    for f in resampler.resample(frame):
                        pcm=f.to_ndarray().tobytes()
                        try:s.sendto(pcm,str(root/"mic.sock"))
                        except (FileNotFoundError,ConnectionRefusedError):pass
        tasks.append(asyncio.create_task(microphone()))
    @peer.on("connectionstatechange")
    async def state():
        if peer.connectionState in {"failed","closed","disconnected"}:
            for t in tasks:t.cancel()
            transport.close()
            c=runtime.store.get(id)
            if c and c.get("takeover"):
                from .models import Command
                import secrets
                await runtime.command(id,Command(command_id=secrets.token_hex(16),kind="release"))
    await peer.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"],type="offer"))
    await peer.setLocalDescription(await peer.createAnswer())
    return {"sdp":peer.localDescription.sdp,"type":peer.localDescription.type,"audio_source":"local_rx_tx_monitor_not_far_end_proof"}
