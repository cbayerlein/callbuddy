import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  TextField,
  Chip,
  Alert,
  Stack,
  MenuItem,
  IconButton,
  Switch,
  FormControlLabel,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  SvgIcon,
  Tooltip,
  LinearProgress,
} from "@mui/material";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "./style.css";

type Row = Record<string, any>;
const paths: Record<string, string> = {
  phone:
    "M6.6 10.8c1.4 2.8 3.8 5.2 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.4c.6 0 1 .4 1 1 0 1.2.2 2.4.6 3.6.1.4 0 .8-.2 1l-2.2 2.2z",
  spark:
    "M12 2c.45 4.9 4.65 9.1 9.55 9.55C16.65 12 12.45 16.2 12 21.1 11.55 16.2 7.35 12 2.45 11.55 7.35 11.1 11.55 6.9 12 2z",
  person:
    "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-3.9 0-7 2.2-7 5v1h14v-1c0-2.8-3.1-5-7-5z",
  history:
    "M13 3a9 9 0 1 1-8.5 12H7a6.5 6.5 0 1 0 1.2-7L11 11H3V3l3.5 3.5A9 9 0 0 1 13 3zm-1 4v6l4 2 1-2-3-1.5V7z",
  settings:
    "M19.4 13a7.2 7.2 0 0 0 0-2l2-1.6-2-3.4-2.4 1a8 8 0 0 0-1.7-1L15 3h-4l-.4 3a8 8 0 0 0-1.7 1l-2.4-1-2 3.4L6.6 11a7.2 7.2 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a8 8 0 0 0 1.7 1L11 21h4l.4-3a8 8 0 0 0 1.7-1l2.4 1 2-3.4zM13 15a3 3 0 1 1 0-6 3 3 0 0 1 0 6z",
  pause: "M6 4h4v16H6zm8 0h4v16h-4z",
  play: "M7 4v16l13-8z",
  mic: "M12 14c1.66 0 3-1.34 3-3V5a3 3 0 0 0-6 0v6c0 1.66 1.34 3 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11z",
  ear: "M12 3a6 6 0 0 0-6 6h2a4 4 0 1 1 8 0c0 2-1 3-2 4-1.5 1.5-2 2-2 4a2 2 0 0 1-4 0H6a4 4 0 0 0 8 0c0-1 .2-1.4 1.4-2.6C16.8 13 18 11.5 18 9a6 6 0 0 0-6-6zm0 4a2 2 0 0 0-2 2v3h2V9h2a2 2 0 0 0-2-2z",
  close:
    "M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z",
  check: "m9 16.17-4.83-4.83-1.42 1.41L9 19 21 7l-1.41-1.41z",
  arrow: "m12 4-1.4 1.4L16.2 11H4v2h12.2l-5.6 5.6L12 20l8-8z",
  plus: "M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z",
  lock: "M17 8V6a5 5 0 0 0-10 0v2H5v14h14V8zm-8-2a3 3 0 0 1 6 0v2H9zm3 12a2 2 0 1 1 0-4 2 2 0 0 1 0 4z",
};
function Icon({ name }: { name: string }) {
  return (
    <SvgIcon aria-hidden="true">
      <path d={paths[name] || paths.spark} />
    </SvgIcon>
  );
}
const uuid = () => {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
};
const apiBase = () => new URL("./api/", location.href).pathname;
async function api(path: string, method = "GET", body?: any) {
  const r = await fetch(apiBase() + path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const d = await r.json();
  if (!r.ok)
    throw new Error(
      typeof d.detail === "string" ? d.detail : "Bitte die Angaben prüfen.",
    );
  return d;
}
const defaultSettings = {
  person: { name: "", callback: "", notes: "" },
  theme: "system",
  language: "de",
  recording: false,
  model_selection: "manual",
  call_budget_eur: 2,
};
const terminal = ["completed", "cancelled", "failed", "inconclusive"];

function App() {
  const [authLoading, setAuthLoading] = useState(true);
  const [auth, setAuth] = useState(false),
    [setup, setSetup] = useState(false),
    [health, setHealth] = useState<Row>({}),
    [password, setPassword] = useState(""),
    [page, setPage] = useState("call"),
    [settings, setSettings] = useState<Row>(defaultSettings),
    [profiles, setProfiles] = useState<Row>({ sip: [], models: [] }),
    [memory, setMemory] = useState<Row[]>([]),
    [calls, setCalls] = useState<Row[]>([]),
    [research, setResearch] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState("restaurant"),
    [number, setNumber] = useState(""),
    [objective, setObjective] = useState(""),
    [brief, setBrief] = useState<Row | null>(null),
    [free, setFree] = useState(""),
    [call, setCall] = useState<Row | null>(null),
    [events, setEvents] = useState<Row[]>([]),
    [instruction, setInstruction] = useState(""),
    [digits, setDigits] = useState(""),
    [mode, setMode] = useState("demo");
  const [selectedMemory, setSelectedMemory] = useState<string[]>([]);
  const [researchJson, setResearchJson] = useState("");
  const [profileDialog, setProfileDialog] = useState<string | null>(null),
    [profileForm, setProfileForm] = useState<Row>({}),
    [memoryText, setMemoryText] = useState(""),
    [memoryEdit, setMemoryEdit] = useState<Row | null>(null),
    [memoryConfirmed, setMemoryConfirmed] = useState(false),
    [follow, setFollow] = useState(true),
    [listening, setListening] = useState(false),
    [speaking, setSpeaking] = useState(false);
  const transcript = useRef<HTMLDivElement>(null),
    audio = useRef<HTMLAudioElement>(null),
    peer = useRef<RTCPeerConnection | null>(null),
    mic = useRef<MediaStream | null>(null),
    cursor = useRef(0);
  const dark =
    settings.theme === "dark" ||
    (settings.theme === "system" &&
      matchMedia("(prefers-color-scheme: dark)").matches);
  const theme = createTheme({
    cssVariables: true,
    palette: {
      mode: dark ? "dark" : "light",
      primary: { main: dark ? "#9cd49f" : "#36693e" },
      secondary: { main: dark ? "#a1ced7" : "#39656c" },
      background: {
        default: dark ? "#101510" : "#f7fbf2",
        paper: dark ? "#1c211c" : "#fff",
      },
      error: { main: dark ? "#ffb4ab" : "#ba1a1a" },
    },
    shape: { borderRadius: 20 },
    typography: {
      fontFamily: "Manrope, sans-serif",
      h3: { fontWeight: 700, letterSpacing: "-.045em" },
      h4: { fontWeight: 700, letterSpacing: "-.035em" },
      h5: { fontWeight: 700 },
      button: { textTransform: "none", fontWeight: 700 },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: { borderRadius: 99, minHeight: 46, paddingInline: 22 },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            boxShadow: "none",
            border: "1px solid",
            borderColor: dark ? "#424940" : "#dde5d9",
            borderRadius: 28,
          },
        },
      },
      MuiTextField: { defaultProps: { fullWidth: true } },
      MuiOutlinedInput: { styleOverrides: { root: { borderRadius: 14 } } },
    },
  });
  async function refresh() {
    const [s, p, m, c, r] = await Promise.all([
      api("settings"),
      api("profiles"),
      api("memory"),
      api("calls"),
      api("research"),
    ]);
    setSettings(s);
    setProfiles(p);
    setMemory(m);
    setCalls(c.reverse());
    setCall((current) => current || c.find((x: Row) => !terminal.includes(x.status)) || null);
    const savedBrief = localStorage.getItem("callbuddy-brief-id");
    if (savedBrief && !c.some((x: Row) => !terminal.includes(x.status))) {
      try { setBrief(await api(`briefs/${savedBrief}`)); }
      catch { localStorage.removeItem("callbuddy-brief-id"); }
    }
    setResearch(r);
    setAuth(true);
  }
  async function action(fn: () => Promise<any>) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    api("health")
      .then(async (h) => {
        setHealth(h);
        setSetup(h.setup_required);
        await refresh().catch(() => setAuth(false));
      })
      .catch(() => setError("Backend ist nicht erreichbar."))
      .finally(() => setAuthLoading(false));
  }, []);
  useEffect(() => {
    if (!call) return;
    cursor.current = 0;
    setEvents([]);
    const es = new EventSource(apiBase() + `calls/${call.id}/events`);
    es.onmessage = (e) => {
      const item = JSON.parse(e.data);
      cursor.current = item.seq;
      setEvents((old) =>
        old.some((x) => x.seq === item.seq) ? old : [...old, item],
      );
      if (item.kind === "state" || item.kind === "decision")
        api(`calls/${call.id}`)
          .then(setCall)
          .catch(() => {});
    };
    es.onerror = () =>
      setNotice(
        "Verbindung wird wieder aufgenommen; Befehle werden nicht erneut gesendet.",
      );
    return () => es.close();
  }, [call?.id]);
  useEffect(() => {
    if (follow)
      transcript.current?.scrollTo({
        top: transcript.current.scrollHeight,
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
  }, [events, follow]);
  useEffect(
    () => () => {
      peer.current?.close();
      mic.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );
  useEffect(() => {
    if (!call || terminal.includes(call.status)) {
      peer.current?.close();
      peer.current = null;
      mic.current?.getTracks().forEach((t) => t.stop());
      mic.current = null;
      setListening(false);
      setSpeaking(false);
    }
  }, [call?.id, call?.status]);
  const saveSettings = () =>
    action(async () => {
      setSettings(await api("settings", "PUT", settings));
      setNotice("Einstellungen gespeichert.");
    });
  function navigate(p: string) {
    setPage(p);
    setNotice("");
    setTimeout(
      () => document.querySelector<HTMLElement>("main h1")?.focus(),
      0,
    );
  }
  async function beginPrep() {
    const b = await api("briefs", "POST", {
      number,
      objective,
      scenario,
      memory_ids: selectedMemory,
      model_profile: settings.model_selection === "recommended" ? null : settings.default_model || null,
      sip_profile: settings.default_sip || null,
    });
    setBrief(await api(`briefs/${b.id}`));
    localStorage.setItem("callbuddy-brief-id", b.id);
    setCall(null);
    setFree("");
  }
  async function answerPrep(answer: string) {
    if (!brief) return;
    setBrief(
      await api(`briefs/${brief.id}/answers`, "POST", {
        question_id: brief.question.id,
        answer,
      }),
    );
    setFree("");
  }
  async function cmd(kind: string, text = "") {
    if (!call) return;
    await api(`calls/${call.id}/commands`, "POST", {
      command_id: uuid(),
      kind,
      text,
    });
    setCall(await api(`calls/${call.id}`));
  }
  async function connectAudio(withMic = false) {
    if (!call) return;
    if (withMic && (!isSecureContext || !navigator.mediaDevices))
      throw new Error("Für das Mikrofon ist ein HTTPS-Zugang erforderlich. Textsteuerung bleibt verfügbar.");
    if (!window.RTCPeerConnection)
      throw new Error(
        "Browser-Audio nicht verfügbar. Textsteuerung bleibt möglich.",
      );
    peer.current?.close();
    mic.current?.getTracks().forEach((t) => t.stop());
    const p = new RTCPeerConnection();
    peer.current = p;
    try {
    p.ontrack = (e) => {
      if (audio.current) {
        audio.current.srcObject = e.streams[0] || new MediaStream([e.track]);
        audio.current
          .play()
          .catch(() =>
            setNotice("Bitte Audio-Wiedergabe im Browser erlauben."),
          );
      }
    };
    if (withMic) {
      mic.current = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      for (const t of mic.current.getAudioTracks()) p.addTrack(t, mic.current);
    } else p.addTransceiver("audio", { direction: "recvonly" });
    await p.setLocalDescription(await p.createOffer());
    if (p.iceGatheringState !== "complete")
      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, 5000);
        p.addEventListener("icegatheringstatechange", () => {
          if (p.iceGatheringState === "complete") {
            clearTimeout(timer);
            resolve();
          }
        });
      });
    const answer = await api(`calls/${call.id}/rtc`, "POST", {
      sdp: p.localDescription!.sdp,
      type: "offer",
    });
    await p.setRemoteDescription(answer);
    setListening(true);
    if (withMic) {
      await cmd("takeover");
      setSpeaking(true);
    }
    if (call.mode === "demo")
      setNotice(
        "Demo: Der Audiokanal liefert Stille. Kein echter Gesprächston.",
      );
    } catch (error) {
      p.close();
      mic.current?.getTracks().forEach((t) => t.stop());
      mic.current = null;
      peer.current = null;
      setListening(false);
      setSpeaking(false);
      throw error;
    }
  }
  async function stopSpeaking() {
    mic.current?.getTracks().forEach((t) => t.stop());
    setSpeaking(false);
    await cmd("release");
    setNotice(
      "Mikrofon aus. Modellstimme bleibt pausiert, bis du sie fortsetzt.",
    );
  }
  function openProfile(kind: string, old?: Row) {
    setProfileDialog(kind);
    setProfileForm(
      old
        ? { ...old, password: "", api_key: "" }
        : kind === "sip"
          ? {
              name: "",
              username: "",
              auth_id: "",
              domain: "",
              registrar: "",
              port: 5060,
              proxy: "",
              transport: "udp",
              caller_id: "",
              stun: "",
              password: "",
              phone_eur_per_minute: 0,
              pricing_confirmed: false,
            }
          : {
              name: "",
              provider: "openai",
              model: "gpt-realtime-2.1",
              prep_model: "",
              voice: "marin",
              language: "de",
              api_key: "",
              eagerness: "auto",
              maximum_token_eur_per_million: 100,
              pricing_confirmed: false,
            },
    );
  }
  const field = (key: string, label: string, extra: Row = {}) => (
    <TextField
      key={key}
      label={label}
      value={profileForm[key] ?? ""}
      onChange={(e) =>
        setProfileForm({
          ...profileForm,
          [key]:
            extra.type === "number" ? Number(e.target.value) : e.target.value,
        })
      }
      {...extra}
    />
  );
  async function saveProfile() {
    const { id, has_credential, qualification, profile_kind, ...body } =
      profileForm;
    if (!body.password) delete body.password;
    if (!body.api_key) delete body.api_key;
    await api(
      `profiles/${profileDialog}${id ? "/" + id : ""}`,
      id ? "PUT" : "POST",
      body,
    );
    setProfileDialog(null);
    await refresh();
    setNotice("Profil gespeichert. Live-Abnahme steht noch aus.");
  }
  const tabs = [
    ["call", "phone", "Anrufen"],
    ["history", "history", "Verlauf"],
    ["memory", "person", "Mein Profil"],
    ["settings", "settings", "Einstellungen"],
  ];
  const head = (eyebrow: string, title: string, description: string) => (
    <Box className="page-head">
      <Typography className="eyebrow">{eyebrow}</Typography>
      <Typography component="h1" variant="h3" tabIndex={-1}>
        {title}
      </Typography>
      <Typography color="text.secondary" sx={{ maxWidth: 650, mt: 1.5 }}>
        {description}
      </Typography>
    </Box>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <a className="skip" href="#content">
        Zum Inhalt springen
      </a>
      <Box className="shell">
        <Box component="aside" className="rail">
          <Box className="brand">
            <Box className="brand-mark">
              <Icon name="spark" />
            </Box>
            <Box>
              <Typography sx={{ fontWeight: 700 }}>CallBuddy</Typography>
              <Typography variant="caption" color="text.secondary">
                Deine Telefonassistenz
              </Typography>
            </Box>
          </Box>
          <Box
            component="nav"
            aria-label="Hauptnavigation"
            className="navigation"
          >
            {tabs.map(([p, i, t]) => (
              <Button
                key={p}
                startIcon={<Icon name={i} />}
                className={page === p ? "selected" : ""}
                aria-current={page === p ? "page" : undefined}
                onClick={() => navigate(p)}
              >
                {t}
              </Button>
            ))}
          </Box>
          <Box className="rail-note">
            <Icon name="lock" />
            <Typography variant="body2">
              Dein Auftrag.
              <br />
              Deine Entscheidungen.
            </Typography>
          </Box>
        </Box>
        <Box component="main" id="content" className="main">
          <Box className="topline">
            <Typography variant="body2" color="text.secondary">
              TELEFONASSISTENZ / {tabs.find((t) => t[0] === page)?.[2]}
            </Typography>
            <Chip
              size="small"
              icon={<Icon name="lock" />}
              label="Eigene Installation"
            />
          </Box>
          {!isSecureContext && <Alert severity="info" sx={{mb: 2}}>HTTP-Vorschau: Bitte nur Demo-Daten verwenden, keine echten SIP-/API-Zugangsdaten. Mikrofon und regulärer Betrieb benötigen HTTPS.</Alert>}
          {error && (
            <Alert
              severity="error"
              role="alert"
              onClose={() => setError("")}
              sx={{ mb: 2 }}
            >
              {error}
            </Alert>
          )}
          {notice && (
            <Alert
              severity="info"
              role="status"
              onClose={() => setNotice("")}
              sx={{ mb: 2 }}
            >
              {notice}
            </Alert>
          )}
          {busy && (
            <LinearProgress aria-label="Wird verarbeitet" sx={{ mb: 2 }} />
          )}
          {authLoading ? <LinearProgress aria-label="Anmeldung wird geprüft" /> : !auth ? (
            <Box className="auth-card">
              <Box className="brand-mark" sx={{ mb: 3 }}>
                <Icon name="spark" />
              </Box>
              {head(
                "WILLKOMMEN",
                setup
                  ? "Deine Assistenz. Dein Zugang."
                  : "Schön, dass du da bist.",
                "Melde dich an, um deine Einstellungen, dein Memory und deine Gespräche zu öffnen.",
              )}
              <Card>
                <CardContent>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      action(async () => {
                        await api("auth", "POST", { password });
                        setPassword("");
                        await refresh();
                      });
                    }}
                  >
                    <Stack spacing={3}>
                      <TextField
                        label={setup ? "Neues Passwort" : "Passwort"}
                        type="password"
                        autoComplete={
                          setup ? "new-password" : "current-password"
                        }
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        helperText="Mindestens 12 Zeichen. Der Zugang gehört nur dieser Installation."
                      />
                      <Button
                        type="submit"
                        variant="contained"
                        disabled={busy || password.length < 12}
                        endIcon={<Icon name="arrow" />}
                      >
                        {setup ? "Zugang einrichten" : "Anmelden"}
                      </Button>
                    </Stack>
                  </form>
                </CardContent>
              </Card>
            </Box>
          ) : (
            <>
              {page === "call" && (
                <>
                  {call ? (
                    <>
                      {head(
                        call.mode === "demo"
                          ? "DEMO · KEINE TELEFONIE"
                          : "LIVE-GESPRÄCH",
                        call.objective,
                        "Bleib dabei, entscheide bei Rückfragen und greife jederzeit ein.",
                      )}
                      <Box className="live-grid">
                        <Card>
                          <CardContent>
                            <Stack
                              direction="row"
                              spacing={1}
                              sx={{ mb: 2, flexWrap: "wrap" }}
                            >
                              <Chip
                                color="primary"
                                label={
                                  (
                                    {
                                      preparing: "Vorbereiten",
                                      connected: "Verbunden",
                                      awaiting_user: "Deine Entscheidung",
                                      completed: "Beendet",
                                      cancelled: "Abgebrochen",
                                      inconclusive: "Ungeklärt",
                                      dialling: "Wählt",
                                    } as Row
                                  )[call.status] || call.status
                                }
                              />
                              <Chip
                                label={
                                  call.mode === "demo" ? "Simulation" : "SIP"
                                }
                              />
                              <Chip
                                label={
                                  terminal.includes(call.status) ? "Audiokanal beendet" : call.paused
                                    ? "Modellstimme pausiert"
                                    : "Modellstimme aktiv"
                                }
                              />
                            </Stack>
                            <Typography component="h2" variant="h6">
                              Gespräch
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Erkennung kann ungenau sein. Demo-Texte sind
                              ausdrücklich simuliert.
                            </Typography>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={follow}
                                  onChange={(e) => setFollow(e.target.checked)}
                                />
                              }
                              label="Neue Zeilen verfolgen"
                            />
                            <Box
                              ref={transcript}
                              className="transcript"
                              role="log"
                              aria-label="Gesprächstranskript"
                              aria-live="off"
                            >
                              {events
                                .filter((e) =>
                                  [
                                    "transcript",
                                    "decision_answer",
                                    "private_instruction",
                                  ].includes(e.kind),
                                )
                                .map((e) => (
                                  <Box
                                    key={e.seq}
                                    className={"bubble " + e.speaker}
                                  >
                                    <Typography className="speaker">
                                      {e.speaker === "callee"
                                        ? "Gegenstelle"
                                        : e.speaker === "assistant"
                                          ? "Assistenz"
                                          : "Du · privat"}{" "}
                                      ·{" "}
                                      {e.source === "demo_script"
                                        ? "Demo"
                                        : e.source === "recognition"
                                          ? "Erkannt"
                                          : e.source === "model_output"
                                            ? "Modellausgabe"
                                            : "Private Eingabe"}
                                    </Typography>
                                    <Typography>{e.text}</Typography>
                                  </Box>
                                ))}
                              {!events.some((e) => e.kind === "transcript") && (
                                <Typography color="text.secondary">
                                  Das Gespräch beginnt …
                                </Typography>
                              )}
                            </Box>
                          </CardContent>
                        </Card>
                        <Stack spacing={2}>
                          {call.decision && (
                            <Card className="decision-card">
                              <CardContent>
                                <Chip
                                  icon={<Icon name="person" />}
                                  label="Nur für dich"
                                  color="secondary"
                                />
                                <Typography
                                  component="h2"
                                  variant="h6"
                                  sx={{ mt: 2 }}
                                >
                                  {call.decision.question}
                                </Typography>
                                <Typography
                                  variant="body2"
                                  color="text.secondary"
                                  sx={{ my: 1 }}
                                >
                                  Die Assistenz entscheidet nicht an deiner
                                  Stelle.
                                </Typography>
                                <Stack spacing={1}>
                                  {call.decision.options.map((o: string) => (
                                    <Button
                                      key={o}
                                      variant="outlined"
                                      sx={{
                                        justifyContent: "flex-start",
                                        textAlign: "left",
                                      }}
                                      onClick={() =>
                                        action(async () => {
                                          await api(
                                            `calls/${call.id}/decisions/${call.decision.id}/answer`,
                                            "POST",
                                            { answer: o },
                                          );
                                          setCall(
                                            await api(`calls/${call.id}`),
                                          );
                                        })
                                      }
                                    >
                                      {o}
                                    </Button>
                                  ))}
                                  <TextField
                                    label="Eigene Antwort"
                                    multiline
                                    value={free}
                                    onChange={(e) => setFree(e.target.value)}
                                  />
                                  <Button
                                    disabled={!free.trim()}
                                    onClick={() =>
                                      action(async () => {
                                        await api(
                                          `calls/${call.id}/decisions/${call.decision.id}/answer`,
                                          "POST",
                                          { answer: free },
                                        );
                                        setFree("");
                                        setCall(await api(`calls/${call.id}`));
                                      })
                                    }
                                  >
                                    Antwort senden
                                  </Button>
                                </Stack>
                              </CardContent>
                            </Card>
                          )}
                          <Card>
                            <CardContent>
                              <Typography component="h2" variant="h6">
                                Private Anweisung
                              </Typography>
                              <Typography
                                variant="body2"
                                color="text.secondary"
                                sx={{ mb: 2 }}
                              >
                                Wird an die Assistenz geschickt, nicht zur
                                Gegenstelle gesprochen.
                              </Typography>
                              <TextField
                                label="Was soll die Assistenz beachten?"
                                multiline
                                minRows={3}
                                value={instruction}
                                onChange={(e) => setInstruction(e.target.value)}
                                disabled={terminal.includes(call.status)}
                              />
                              <Button
                                variant="outlined"
                                sx={{ mt: 2 }}
                                disabled={
                                  !instruction.trim() ||
                                  terminal.includes(call.status)
                                }
                                onClick={() =>
                                  action(async () => {
                                    await cmd("instruction", instruction);
                                    setInstruction("");
                                  })
                                }
                              >
                                Anweisung senden
                              </Button>
                            </CardContent>
                          </Card>
                          <Card>
                            <CardContent>
                              <Typography variant="body2">
                                Budget: {call.budget_eur.toFixed(2)} € ·
                                Schätzung:{" "}
                                {(call.estimated_eur || 0).toFixed(2)} €
                              </Typography>
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {call.mode === "demo"
                                  ? "Keine Anbieter- oder Telefonkosten."
                                  : "Keine verifizierte Rechnung."}
                              </Typography>
                            </CardContent>
                          </Card>
                        </Stack>
                      </Box>
                      {terminal.includes(call.status) ? (
                        <Alert
                          severity={
                            call.status === "completed" ? "info" : "warning"
                          }
                          sx={{ mt: 3 }}
                        >
                          <Typography sx={{ fontWeight: 700 }}>
                            Ergebnis
                          </Typography>
                          {call.result}
                          <Stack direction="row" sx={{gap: 1, flexWrap: "wrap", my: 2}}>
                            <Button component="a" href={apiBase()+`calls/${call.id}/transcript`} download>Transkript herunterladen</Button>
                            {call.mode === "live" && settings.recording && <Button component="a" href={apiBase()+`calls/${call.id}/audio`} download>Audio herunterladen</Button>}
                            <Button disabled={busy || !settings.default_model || call.mode === "demo"} onClick={() => action(async () => {
                              await api(`calls/${call.id}/memory-proposals`, "POST", {model_profile: settings.default_model, request_id: uuid(), budget_eur: 0.25});
                              await refresh();
                              navigate("profile");
                              setNotice("KI-Vorschläge sind unbestätigt. Bitte einzeln prüfen.");
                            })}>Memory-Vorschläge (max. 0,25 €)</Button>
                          </Stack>
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            Cleanup: {call.cleanup}
                          </Typography>
                          <Button
                            sx={{ mt: 1 }}
                            onClick={() => {
                              setCall(null);
                              setBrief(null);
                              refresh();
                            }}
                          >
                            Neues Gespräch vorbereiten
                          </Button>
                        </Alert>
                      ) : (
                        <Card className="call-controls">
                          <CardContent>
                            <Stack
                              direction="row"
                              sx={{ gap: 1, flexWrap: "wrap" }}
                            >
                              <Button
                                startIcon={
                                  <Icon name={call.paused ? "play" : "pause"} />
                                }
                                variant="outlined"
                                onClick={() =>
                                  action(() =>
                                    cmd(call.paused ? "resume" : "pause"),
                                  )
                                }
                              >
                                {call.paused ? "Fortsetzen" : "Pausieren"}
                              </Button>
                              <Button
                                startIcon={<Icon name="ear" />}
                                onClick={() => action(() => connectAudio())}
                              >
                                {listening ? "Audio verbinden" : "Mithören"}
                              </Button>
                              <Button
                                startIcon={<Icon name="mic" />}
                                variant={speaking ? "contained" : "outlined"}
                                onClick={() =>
                                  action(() =>
                                    speaking
                                      ? stopSpeaking()
                                      : connectAudio(true),
                                  )
                                }
                              >
                                {speaking
                                  ? "Mikrofon beenden"
                                  : "Selbst sprechen"}
                              </Button>
                              <Button
                                color="error"
                                variant="contained"
                                startIcon={<Icon name="close" />}
                                onClick={() => action(() => cmd("hangup"))}
                              >
                                Auflegen
                              </Button>
                            </Stack>
                            <Stack
                              direction="row"
                              spacing={1}
                              sx={{ mt: 2, maxWidth: 320 }}
                            >
                              <TextField
                                label="Tastenfolge (DTMF)"
                                size="small"
                                value={digits}
                                onChange={(e) => setDigits(e.target.value)}
                                slotProps={{ htmlInput: { maxLength: 32 } }}
                              />
                              <Button
                                disabled={!digits}
                                onClick={() =>
                                  action(async () => {
                                    await cmd("dtmf", digits);
                                    setDigits("");
                                  })
                                }
                              >
                                Senden
                              </Button>
                            </Stack>
                          </CardContent>
                        </Card>
                      )}
                      <audio ref={audio} autoPlay />
                    </>
                  ) : brief ? (
                    <>
                      {head(
                        "VORBEREITUNG",
                        "Ein guter Anruf beginnt hier.",
                        "Wir klären die wichtigen Angaben vorab. Du behältst die Entscheidung über neue Zusagen.",
                      )}
                      <Box className="prep-layout">
                        <Card>
                          <CardContent>
                            <Typography variant="overline">
                              {brief.scenario === "restaurant"
                                ? "Restaurant"
                                : brief.scenario === "doctor"
                                  ? "Arztpraxis"
                                  : brief.scenario === "airline"
                                    ? "Fluggesellschaft"
                                    : "Dein Anliegen"}
                            </Typography>
                            <Button disabled={busy || !settings.default_model} onClick={() => action(async () => {
                              setBrief(await api(`briefs/${brief.id}/prepare-ai`, "POST", {model_profile: settings.default_model, request_id: uuid(), budget_eur: 0.25}));
                            })}>Zusätzliche KI-Vorbereitung (max. 0,25 €)</Button>
                            <Typography
                              component="h2"
                              variant="h5"
                              sx={{ mb: 2 }}
                            >
                              {brief.question
                                ? brief.question.text
                                : "Dein Anruf-Steckbrief"}
                            </Typography>
                            {brief.question ? (
                              <Stack spacing={1.5}>
                                {brief.question.options.map((o: string) => (
                                  <Button
                                    key={o}
                                    variant="outlined"
                                    className="choice-button"
                                    onClick={() => action(() => answerPrep(o))}
                                  >
                                    {o}
                                    <Icon name="arrow" />
                                  </Button>
                                ))}
                                <TextField
                                  label="Eigene Angabe"
                                  multiline
                                  minRows={2}
                                  value={free}
                                  onChange={(e) => setFree(e.target.value)}
                                />
                                <Button
                                  variant="contained"
                                  disabled={!free.trim()}
                                  onClick={() => action(() => answerPrep(free))}
                                  endIcon={<Icon name="arrow" />}
                                >
                                  Weiter
                                </Button>
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                >
                                  Aktuell regelbasierte Vorbereitung ohne
                                  API-Kosten. KI-Vorbereitung folgt über die
                                  Modelladapter.
                                </Typography>
                              </Stack>
                            ) : (
                              <Stack spacing={2}>
                                <Typography>{brief.objective}</Typography>
                                <Typography color="text.secondary">
                                  Zielnummer: {brief.number}
                                </Typography>
                                {Object.entries(brief.answers).map(([k, v]) => (
                                  <TextField
                                    key={k}
                                    label={
                                      k === "permissions"
                                        ? "Erlaubte Alternativen"
                                        : k
                                    }
                                    multiline
                                    value={v as string}
                                    onChange={(e) =>
                                      setBrief({
                                        ...brief,
                                        answers: {
                                          ...brief.answers,
                                          [k]: e.target.value,
                                        },
                                        accepted: false,
                                      })
                                    }
                                  />
                                ))}
                                <Button
                                  variant="outlined"
                                  onClick={() =>
                                    action(async () => {
                                      const {
                                        id,
                                        revision,
                                        accepted,
                                        question,
                                        context,
                                        accepted_context,
                                        ...b
                                      } = brief;
                                      setBrief({
                                        ...(await api(
                                          `briefs/${id}`,
                                          "PUT",
                                          b,
                                        )),
                                        question: null,
                                      });
                                    })
                                  }
                                >
                                  Änderungen speichern
                                </Button>
                                <Button
                                  variant="contained"
                                  startIcon={<Icon name="check" />}
                                  onClick={() =>
                                    action(async () =>
                                      setBrief({
                                        ...(await api(
                                          `briefs/${brief.id}/accept`,
                                          "POST",
                                          {},
                                        )),
                                        question: null,
                                      }),
                                    )
                                  }
                                >
                                  {brief.accepted
                                    ? "Steckbrief freigegeben"
                                    : "Steckbrief freigeben"}
                                </Button>
                                <Divider />
                                <TextField
                                  select
                                  label="Gesprächsmodus"
                                  value={mode}
                                  onChange={(e) => setMode(e.target.value)}
                                >
                                  <MenuItem value="demo">
                                    Demo – keine Telefonie, keine API-Kosten
                                  </MenuItem>
                                  <MenuItem value="live">
                                    Live – SIP und ausgewähltes Modell
                                  </MenuItem>
                                </TextField>
                                {!health.live_enabled && mode === "live" && (
                                  <Alert severity="warning">
                                    Live-Telefonie ist bis zur gesonderten
                                    Abnahme gesperrt.
                                  </Alert>
                                )}
                                <Button
                                  variant="contained"
                                  size="large"
                                  startIcon={<Icon name="phone" />}
                                  disabled={
                                    !brief.accepted ||
                                    (mode === "live" && !health.live_enabled)
                                  }
                                  onClick={() =>
                                    action(async () => {
                                      setCall(
                                        await api(
                                          `briefs/${brief.id}/calls`,
                                          "POST",
                                          {
                                            request_id: uuid(),
                                            mode,
                                            accepted_revision: brief.revision,
                                            budget_eur:
                                              settings.call_budget_eur,
                                          },
                                        ),
                                      );
                                      setFree("");
                                      localStorage.removeItem("callbuddy-brief-id");
                                    })
                                  }
                                >
                                  {mode === "demo"
                                    ? "Demo starten"
                                    : "Jetzt anrufen"}
                                </Button>
                              </Stack>
                            )}
                          </CardContent>
                        </Card>
                        <Card className="soft-card">
                          <CardContent>
                            <Icon name="spark" />
                            <Typography
                              component="h2"
                              variant="h6"
                              sx={{ mt: 2 }}
                            >
                              Gut vorbereitet. Nicht festgelegt.
                            </Typography>
                            <Typography color="text.secondary" sx={{ mt: 1 }}>
                              Offene Angaben bleiben offen. Bei neuen
                              Entscheidungen fragt deine Assistenz dich.
                            </Typography>
                            <Divider sx={{ my: 3 }} />
                            <Typography variant="body2">
                              {Object.keys(brief.answers).length} Angaben
                              geklärt
                            </Typography>
                            <Button
                              sx={{ mt: 2 }}
                              onClick={() => {
                                setBrief(null);
                                setFree("");
                              }}
                            >
                              Vorbereitung verlassen
                            </Button>
                          </CardContent>
                        </Card>
                      </Box>
                    </>
                  ) : (
                    <>
                      {head(
                        "IN DEINEM AUFTRAG",
                        "Du entscheidest.\nWir führen das Gespräch.",
                        "Reservierungen, Termine und Rückfragen – gut vorbereitet und mit dir am Steuer.",
                      )}
                      <Box className="start-grid">
                        <Card className="start-card">
                          <CardContent>
                            <Typography
                              component="h2"
                              variant="h5"
                              sx={{ mb: 3 }}
                            >
                              Was möchtest du erledigen?
                            </Typography>
                            <form
                              onSubmit={(e) => {
                                e.preventDefault();
                                action(beginPrep);
                              }}
                            >
                              <Stack spacing={2.5}>
                                <Typography variant="body2">Nur ausgewählte, bestätigte persönliche Angaben werden mitgegeben.</Typography>
                                {memory.filter((m) => m.confirmed).map((m) => <FormControlLabel key={m.id} label={m.text} control={<Switch checked={selectedMemory.includes(m.id)} onChange={(_, checked) => setSelectedMemory((old) => checked ? [...old, m.id] : old.filter((id) => id !== m.id))} />} />)}
                                <TextField
                                  select
                                  label="Gesprächsszenario"
                                  value={scenario}
                                  onChange={(e) => setScenario(e.target.value)}
                                >
                                  {[
                                    ["restaurant", "Tisch reservieren"],
                                    ["doctor", "Arzttermin vereinbaren"],
                                    [
                                      "airline",
                                      "Rollstuhl für einen Flug anmelden",
                                    ],
                                    ["general", "Anderes Anliegen"],
                                  ].map(([v, t]) => (
                                    <MenuItem key={v} value={v}>
                                      {t}
                                    </MenuItem>
                                  ))}
                                </TextField>
                                <TextField
                                  label="Telefonnummer"
                                  placeholder="+49 …"
                                  value={number}
                                  onChange={(e) => setNumber(e.target.value)}
                                  helperText="Internationale Rufnummer mit + und Ländervorwahl."
                                  autoComplete="tel"
                                />
                                <TextField
                                  label="Dein Anliegen"
                                  multiline
                                  minRows={3}
                                  value={objective}
                                  onChange={(e) => setObjective(e.target.value)}
                                  placeholder="Ich möchte heute Abend einen Tisch für zwei Personen reservieren."
                                />
                                <Stack direction="row" sx={{ gap: 2 }}>
                                  <TextField
                                    select
                                    label="SIP-Konto"
                                    value={settings.default_sip || ""}
                                    onChange={(e) =>
                                      setSettings({
                                        ...settings,
                                        default_sip: e.target.value,
                                      })
                                    }
                                  >
                                    <MenuItem value="">
                                      Für Demo nicht erforderlich
                                    </MenuItem>
                                    {profiles.sip.map((p: Row) => (
                                      <MenuItem key={p.id} value={p.id}>
                                        {p.name}
                                      </MenuItem>
                                    ))}
                                  </TextField>
                                  <TextField
                                    select
                                    label="Sprachmodell"
                                    value={settings.default_model || ""}
                                    onChange={(e) =>
                                      setSettings({
                                        ...settings,
                                        default_model: e.target.value,
                                      })
                                    }
                                  >
                                    <MenuItem value="">
                                      Für Demo nicht erforderlich
                                    </MenuItem>
                                    {profiles.models.map((p: Row) => (
                                      <MenuItem key={p.id} value={p.id}>
                                        {p.name}
                                      </MenuItem>
                                    ))}
                                  </TextField>
                                </Stack>
                                <Button
                                  variant="contained"
                                  size="large"
                                  type="submit"
                                  disabled={
                                    busy ||
                                    !/^\+[1-9][0-9]{6,14}$/.test(number) ||
                                    objective.length < 3
                                  }
                                  endIcon={<Icon name="arrow" />}
                                >
                                  Anruf vorbereiten
                                </Button>
                              </Stack>
                            </form>
                          </CardContent>
                        </Card>
                        <Stack spacing={2}>
                          <Card className="soft-card">
                            <CardContent>
                              <Box className="illustration" aria-hidden="true">
                                <Icon name="phone" />
                                <span className="orbit orbit-one" />
                                <span className="orbit orbit-two" />
                                <Box className="small-spark">
                                  <Icon name="spark" />
                                </Box>
                              </Box>
                              <Typography component="h2" variant="h5">
                                Nicht allein am Telefon.
                              </Typography>
                              <Typography
                                color="text.secondary"
                                sx={{ mt: 1.5 }}
                              >
                                Deine Assistenz fragt nach, hört zu und holt
                                dich ins Gespräch, wenn du entscheiden möchtest.
                              </Typography>
                            </CardContent>
                          </Card>
                          <Card>
                            <CardContent>
                              <Stack direction="row" spacing={2}>
                                <Icon name="lock" />
                                <Box>
                                  <Typography sx={{ fontWeight: 700 }}>
                                    Dein Profil wird im eigenen Backend gespeichert.
                                  </Typography>
                                  <Typography
                                    variant="body2"
                                    color="text.secondary"
                                  >
                                    Freigegebener Gesprächskontext und Audio werden an den gewählten Modellanbieter übertragen.
                                  </Typography>
                                </Box>
                              </Stack>
                            </CardContent>
                          </Card>
                        </Stack>
                      </Box>
                    </>
                  )}
                </>
              )}
              {page === "history" && (
                <>
                  {head(
                    "VERLAUF",
                    "Was wir gemeinsam geklärt haben.",
                    "Gesprächsergebnisse und offene Punkte – nicht nur eine Liste von Anrufen.",
                  )}
                  <Stack spacing={2}>
                    {calls.length === 0 ? (
                      <Card>
                        <CardContent>
                          <Typography>
                            Noch keine Gespräche. Dein erster Anruf beginnt mit
                            einer Vorbereitung.
                          </Typography>
                        </CardContent>
                      </Card>
                    ) : (
                      calls.map((c) => (
                        <Card key={c.id}>
                          <CardContent>
                            <Stack
                              direction="row"
                              sx={{
                                justifyContent: "space-between",
                                gap: 2,
                                flexWrap: "wrap",
                              }}
                            >
                              <Box>
                                <Typography variant="h6">
                                  {c.objective}
                                </Typography>
                                <Typography color="text.secondary">
                                  {c.destination} ·{" "}
                                  {new Date(c.created_at * 1000).toLocaleString(
                                    "de-DE",
                                  )}
                                </Typography>
                              </Box>
                              <Chip
                                label={c.mode === "demo" ? "Demo" : c.status}
                              />
                            </Stack>
                            <Typography sx={{ mt: 2 }}>
                              {c.result || "Noch kein bestätigtes Ergebnis"}
                            </Typography>
                            <Button
                              sx={{ mt: 1 }}
                              onClick={() => {
                                setCall(c);
                                navigate("call");
                              }}
                            >
                              Gespräch ansehen
                            </Button>
                          </CardContent>
                        </Card>
                      ))
                    )}
                  </Stack>
                </>
              )}
              {page === "memory" && (
                <>
                  {head(
                    "MEIN PROFIL",
                    "Was deine Assistenz wissen darf.",
                    "Bestätigte Angaben werden berücksichtigt. Vorschläge werden erst nach deiner Entscheidung zu Memory.",
                  )}
                  <Box className="settings-grid">
                    <Card>
                      <CardContent>
                        <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
                          Persönliche Angaben
                        </Typography>
                        <Stack spacing={2}>
                          <TextField
                            label="Dein Name"
                            value={settings.person.name}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                person: {
                                  ...settings.person,
                                  name: e.target.value,
                                },
                              })
                            }
                          />
                          <TextField
                            label="Deine Rückrufnummer"
                            value={settings.person.callback}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                person: {
                                  ...settings.person,
                                  callback: e.target.value,
                                },
                              })
                            }
                          />
                          <TextField
                            label="Wichtiger Kontext"
                            multiline
                            minRows={3}
                            value={settings.person.notes}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                person: {
                                  ...settings.person,
                                  notes: e.target.value,
                                },
                              })
                            }
                            helperText="Wird nur als freigegebener Kontext in den Steckbrief aufgenommen."
                          />
                          <Button variant="contained" onClick={saveSettings}>
                            Profil speichern
                          </Button>
                        </Stack>
                      </CardContent>
                    </Card>
                    <Stack spacing={2}>
                      <Card>
                        <CardContent>
                          <Typography component="h2" variant="h6">
                            Memory ergänzen
                          </Typography>
                          <TextField
                            label="Dauerhafte Angabe oder Vorliebe"
                            multiline
                            value={memoryText}
                            onChange={(e) => setMemoryText(e.target.value)}
                            sx={{ mt: 2 }}
                          />
                          <FormControlLabel
                            control={
                              <Switch
                                checked={memoryConfirmed}
                                onChange={(e) =>
                                  setMemoryConfirmed(e.target.checked)
                                }
                              />
                            }
                            label="Ich bestätige diese Angabe"
                          />
                          <Button
                            startIcon={<Icon name="plus" />}
                            disabled={!memoryText.trim()}
                            onClick={() =>
                              action(async () => {
                                await api("memory", "POST", {
                                  text: memoryText,
                                  confirmed: memoryConfirmed,
                                });
                                setMemoryText("");
                                setMemoryConfirmed(false);
                                setMemory(await api("memory"));
                              })
                            }
                          >
                            Eintrag hinzufügen
                          </Button>
                        </CardContent>
                      </Card>
                      {memory.map((m) => (
                        <Card key={m.id}>
                          <CardContent>
                            <Chip
                              size="small"
                              label={
                                m.confirmed
                                  ? "Bestätigt"
                                  : "Vorschlag – nicht verwendet"
                              }
                              color={m.confirmed ? "primary" : "default"}
                            />
                            <Typography sx={{ mt: 2 }}>{m.text}</Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Quelle: {m.source}
                            </Typography>
                            <Stack direction="row">
                              <Button onClick={() => setMemoryEdit(m)}>
                                Bearbeiten
                              </Button>
                              <Button
                                color="error"
                                onClick={() =>
                                  action(async () => {
                                    await api(`memory/${m.id}`, "DELETE");
                                    setMemory(await api("memory"));
                                  })
                                }
                              >
                                Löschen
                              </Button>
                            </Stack>
                          </CardContent>
                        </Card>
                      ))}
                    </Stack>
                  </Box>
                </>
              )}
              {page === "settings" && (
                <>
                  {head(
                    "EINSTELLUNGEN",
                    "Deine Verbindungen. Deine Auswahl.",
                    "SIP und Sprachmodelle sind austauschbar. Zugangsdaten werden ausschließlich im Backend gespeichert.",
                  )}
                  <Box className="settings-grid">
                    <Stack spacing={2}>
                      <Card>
                        <CardContent>
                          <Stack
                            direction="row"
                            sx={{ justifyContent: "space-between" }}
                          >
                            <Typography component="h2" variant="h6">
                              SIP-Konten
                            </Typography>
                            <Button
                              startIcon={<Icon name="plus" />}
                              onClick={() => openProfile("sip")}
                            >
                              Hinzufügen
                            </Button>
                          </Stack>
                          {profiles.sip.length === 0 && (
                            <Typography color="text.secondary" sx={{ mt: 2 }}>
                              Noch kein Konto. Fonial ist eine Voreinstellung –
                              andere SIP-Provider sind manuell konfigurierbar.
                            </Typography>
                          )}
                          {profiles.sip.map((p: Row) => (
                            <Box key={p.id} className="profile-row">
                              <Box>
                                <Typography sx={{ fontWeight: 700 }}>
                                  {p.name}
                                </Typography>
                                <Typography
                                  variant="body2"
                                  color="text.secondary"
                                >
                                  {p.registrar} · {p.transport.toUpperCase()} ·{" "}
                                  {p.has_credential
                                    ? "Zugang gespeichert"
                                    : "Zugang fehlt"}
                                </Typography>
                              </Box>
                              <Button onClick={() => openProfile("sip", p)}>
                                Bearbeiten
                              </Button>
                            </Box>
                          ))}
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent>
                          <Stack
                            direction="row"
                            sx={{ justifyContent: "space-between" }}
                          >
                            <Typography component="h2" variant="h6">
                              Sprachmodelle
                            </Typography>
                            <Button
                              startIcon={<Icon name="plus" />}
                              onClick={() => openProfile("model")}
                            >
                              Hinzufügen
                            </Button>
                          </Stack>
                          {profiles.models.length === 0 && (
                            <Typography color="text.secondary" sx={{ mt: 2 }}>
                              Google oder OpenAI mit eigenen Zugangsdaten
                              einrichten.
                            </Typography>
                          )}
                          {profiles.models.map((p: Row) => (
                            <Box key={p.id} className="profile-row">
                              <Box>
                                <Typography sx={{ fontWeight: 700 }}>
                                  {p.name}
                                </Typography>
                                <Typography
                                  variant="body2"
                                  color="text.secondary"
                                >
                                  {p.provider} · {p.model} · {p.voice}
                                </Typography>
                                <Chip size="small" label="Live-Abnahme offen" />
                              </Box>
                              <Stack>
                                <Button onClick={() => openProfile("model", p)}>
                                  Bearbeiten
                                </Button>
                                <Button
                                  onClick={() =>
                                    action(async () => {
                                      const r = await api(
                                        `profiles/${p.id}/check`,
                                        "POST",
                                        {},
                                      );
                                      setNotice(r.detail);
                                    })
                                  }
                                >
                                  Zugang prüfen
                                </Button>
                              </Stack>
                            </Box>
                          ))}
                        </CardContent>
                      </Card>
                    </Stack>
                    <Stack spacing={2}>
                      <Card>
                        <CardContent>
                          <Typography
                            component="h2"
                            variant="h6"
                            sx={{ mb: 2 }}
                          >
                            Darstellung und Grenzen
                          </Typography>
                          <Stack spacing={2}>
                            <TextField select label="Modellauswahl" value={settings.model_selection} onChange={(e) => setSettings({...settings, model_selection: e.target.value})} helperText="Automatik verwendet ausschließlich geprüfte, explizit freigegebene Empfehlungen.">
                              <MenuItem value="manual">Eigene Auswahl</MenuItem>
                              <MenuItem value="recommended">Freigegebene Empfehlung</MenuItem>
                            </TextField>
                            <TextField
                              select
                              label="Darstellung"
                              value={settings.theme}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  theme: e.target.value,
                                })
                              }
                            >
                              {[
                                ["system", "Wie das System"],
                                ["light", "Hell"],
                                ["dark", "Dunkel"],
                              ].map(([v, t]) => (
                                <MenuItem key={v} value={v}>
                                  {t}
                                </MenuItem>
                              ))}
                            </TextField>
                            <TextField
                              select
                              label="Gesprächssprache"
                              value={settings.language}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  language: e.target.value,
                                })
                              }
                            >
                              <MenuItem value="de">Deutsch</MenuItem>
                              <MenuItem value="en">English</MenuItem>
                            </TextField>
                            <TextField
                              label="Budget pro Anruf (€)"
                              type="number"
                              value={settings.call_budget_eur}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  call_budget_eur: Number(e.target.value),
                                })
                              }
                            />
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={settings.recording}
                                  onChange={(e) =>
                                    setSettings({
                                      ...settings,
                                      recording: e.target.checked,
                                    })
                                  }
                                />
                              }
                              label="Gesprächsaudio aufzeichnen"
                            />
                            <Button variant="contained" onClick={saveSettings}>
                              Einstellungen speichern
                            </Button>
                          </Stack>
                        </CardContent>
                      </Card>
                      <Card className="soft-card">
                        <CardContent>
                          <Icon name="spark" />
                          <Typography
                            component="h2"
                            variant="h6"
                            sx={{ mt: 1 }}
                          >
                            Forschung ohne Überraschungen
                          </Typography>
                          <Typography color="text.secondary" sx={{ my: 1 }}>
                            Neue Erkenntnisse werden als versionierte Kandidaten
                            geprüft. Laufende Gespräche verändern sich dadurch
                            nicht.
                          </Typography>
                          {research.length ? (
                            research.map((r) => (
                              <Box key={r.id} sx={{my: 2}}>
                                <Typography variant="body2">{r.name}: {r.status}</Typography>
                                <Typography variant="caption">Quelle: {r.source_hash} · Audio: {r.measured_audio ? "gemessen" : "offen"} · Hörprüfung: {r.human_listening_approved ? "bestätigt" : "offen"}</Typography>
                                {r.status !== "approved" && <Button disabled={!r.measured_audio || !r.human_listening_approved || !r.role_and_reference_passed} onClick={() => action(async () => {
                                  await api(`research/${r.id}/approve`, "POST", {}); await refresh();
                                })}>Geprüften Kandidaten freigeben</Button>}
                              </Box>
                            ))
                          ) : (
                            <Chip label="Noch keine freigegebene Empfehlung" />
                          )}
                          <TextField sx={{mt: 2}} label="Versionierten Forschungskandidaten importieren (JSON)" multiline minRows={3} value={researchJson} onChange={(e) => setResearchJson(e.target.value)} helperText="Import allein ist keine Qualifikation. Nur tatsächlich geprüfte Evidenz angeben." />
                          <Button disabled={!researchJson || busy} onClick={() => action(async () => {
                            const candidate = JSON.parse(researchJson);
                            await api("research", "POST", candidate); setResearchJson(""); await refresh();
                          })}>Kandidat importieren</Button>
                        </CardContent>
                      </Card>
                      <Button
                        onClick={() =>
                          action(async () => {
                            await api("auth", "DELETE");
                            setAuth(false);
                          })
                        }
                      >
                        Abmelden
                      </Button>
                    </Stack>
                  </Box>
                </>
              )}
            </>
          )}
        </Box>
      </Box>
      <Dialog
        open={!!profileDialog}
        onClose={() => setProfileDialog(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>
          {profileDialog === "sip"
            ? "SIP-Konto einrichten"
            : "Sprachmodell einrichten"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {field("name", "Profilname")}
            {profileDialog === "sip" ? (
              <>
                <Button
                  onClick={() =>
                    setProfileForm({
                      ...profileForm,
                      name: "Fonial",
                      domain: "sip.plusnet.de",
                      registrar: "sip.plusnet.de",
                      transport: "udp",
                      port: 5060,
                    })
                  }
                >
                  Fonial-Voreinstellung verwenden
                </Button>
                {field("username", "Benutzername")}
                {field("auth_id", "Authentifizierungs-ID (optional)")}
                {field("password", "Passwort", {
                  type: "password",
                  autoComplete: "new-password",
                  helperText: profileForm.has_credential
                    ? "Leer lassen, um das gespeicherte Passwort zu behalten."
                    : "Wird nur an dein Backend übergeben.",
                })}
                {field("domain", "SIP-Domain")}
                {field("registrar", "Registrar-Hostname")}
                {field("port", "Port", { type: "number" })}
                {field("proxy", "Outbound-Proxy (optional)")}
                {field("transport", "Transport", {
                  select: true,
                  children: ["udp", "tcp", "tls"].map((v) => (
                    <MenuItem key={v} value={v}>
                      {v.toUpperCase()}
                    </MenuItem>
                  )),
                })}
                {field("caller_id", "Absendernummer (optional)")}
                {field("stun", "STUN-Server (optional)")}
                {field("phone_eur_per_minute", "Telefontarif €/Minute", {
                  type: "number",
                })}
              </>
            ) : (
              <>
                {field("provider", "Anbieter", {
                  select: true,
                  children: [
                    <MenuItem key="o" value="openai">
                      OpenAI
                    </MenuItem>,
                    <MenuItem key="g" value="google">
                      Google
                    </MenuItem>,
                  ],
                })}
                {field("model", "Live-Modell-ID")}
                {field("prep_model", "Vorbereitungsmodell (optional)")}
                {field("voice", "Stimme")}
                {field("language", "Sprache", {
                  select: true,
                  children: [
                    <MenuItem key="d" value="de">
                      Deutsch
                    </MenuItem>,
                    <MenuItem key="e" value="en">
                      English
                    </MenuItem>,
                  ],
                })}
                {field("api_key", "API-Schlüssel", {
                  type: "password",
                  autoComplete: "new-password",
                  helperText:
                    "Gespeicherte Schlüssel werden nie zurück angezeigt.",
                })}
                {field("eagerness", "Turn-Erkennung", {
                  select: true,
                  children: ["auto", "low", "medium", "high"].map((v) => (
                    <MenuItem key={v} value={v}>
                      {v}
                    </MenuItem>
                  )),
                })}
                {field(
                  "maximum_token_eur_per_million",
                  "Konservative maximale €/Mio. Tokens",
                  {
                    type: "number",
                    helperText:
                      "Muss die teuerste verwendete Eingabe-/Ausgabekategorie abdecken.",
                  },
                )}
              </>
            )}
            <FormControlLabel
              control={
                <Switch
                  checked={!!profileForm.pricing_confirmed}
                  onChange={(e) =>
                    setProfileForm({
                      ...profileForm,
                      pricing_confirmed: e.target.checked,
                    })
                  }
                />
              }
              label="Tarif geprüft und bestätigt"
            />
            <Alert severity="info">
              Speichern ist keine Live-Abnahme. Keine automatische Registrierung
              oder kostenpflichtige Audio-Probe.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProfileDialog(null)}>Abbrechen</Button>
          <Button variant="contained" onClick={() => action(saveProfile)}>
            Speichern
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog open={!!memoryEdit} onClose={() => setMemoryEdit(null)} fullWidth>
        <DialogTitle>Memory bearbeiten</DialogTitle>
        <DialogContent>
          {memoryEdit && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                label="Angabe"
                multiline
                value={memoryEdit.text}
                onChange={(e) =>
                  setMemoryEdit({ ...memoryEdit, text: e.target.value })
                }
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={memoryEdit.confirmed}
                    onChange={(e) =>
                      setMemoryEdit({
                        ...memoryEdit,
                        confirmed: e.target.checked,
                      })
                    }
                  />
                }
                label="Von mir bestätigt"
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMemoryEdit(null)}>Abbrechen</Button>
          <Button
            onClick={() =>
              action(async () => {
                const { id, updated_at, ...m } = memoryEdit!;
                await api(`memory/${id}`, "PUT", m);
                setMemoryEdit(null);
                setMemory(await api("memory"));
              })
            }
          >
            Speichern
          </Button>
        </DialogActions>
      </Dialog>
    </ThemeProvider>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
