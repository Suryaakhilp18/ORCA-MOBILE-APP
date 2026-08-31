// ORCA API client. All calls hit the FastAPI backend via EXPO_PUBLIC_BACKEND_URL.
// Every function throws on network failure so screens can fall back to cache.
const BASE = (process.env.EXPO_PUBLIC_BACKEND_URL || "") + "/api";

async function req(path: string, options?: RequestInit) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export type Marker = { lat: number; lon: number; label: string; kind: string };
export type MapWidgetT = {
  type: "map";
  center: { lat: number; lon: number };
  markers: Marker[];
  layers: any[];
};
export type ChartWidgetT = {
  type: "chart";
  title: string;
  unit: string;
  labels: string[];
  values: number[];
  color: string;
};
export type Widget = MapWidgetT | ChartWidgetT;

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  verdict?: string | null;
  citations?: string[];
  widgets?: Widget[];
  reasoning_trace?: { agent: string; detail: string }[];
  intent?: string;
};

export type Region = {
  id: string;
  name: string;
  state: string;
  center: { lat: number; lon: number };
  sea?: string;
  coast_bearing?: string;
};

export type GeoResult = { display_name: string; lat: number; lon: number; type?: string };

export type WeatherSnapshot = {
  wind_kn: number;
  gust_kn: number;
  wave_m: number;
  condition: string;
  lightning_pct: number;
  cyclone: string | null;
  timeframe: string;
};

export type TrendSeries = { unit: string; labels: string[]; values: number[] };

export type Situation = {
  region: string;
  region_id: string;
  severity: "critical" | "warning" | "advisory";
  verdict: string;
  reasons: string[];
  weather_today: WeatherSnapshot;
  weather_tomorrow: WeatherSnapshot;
  alerts: any[];
  tide: { type: string; time: string; height_m: number }[];
  trends: { wind: TrendSeries; wave: TrendSeries; sst: TrendSeries };
  generated_at: string;
};

export const api = {
  chat: (body: {
    message: string;
    session_id: string;
    language?: string | null;
    location?: { name?: string; lat: number; lon: number } | null;
    region_id?: string | null;
    user_id?: string;
  }) => req("/chat", { method: "POST", body: JSON.stringify(body) }),

  getConversation: (session_id: string) =>
    req(`/conversations/${session_id}`),

  getAlerts: (region_id?: string) =>
    req(`/alerts${region_id ? `?region_id=${region_id}` : ""}`),
  getNotifications: (user_id = "demo-user") =>
    req(`/notifications?user_id=${user_id}`),
  getSituation: (region_id?: string): Promise<Situation> =>
    req(`/situation${region_id ? `?region_id=${region_id}` : ""}`),
  voiceTranscribe: async (fileUri: string, language: string): Promise<{ text: string }> => {
    const form = new FormData();
    form.append("audio", { uri: fileUri, name: "voice.m4a", type: "audio/m4a" } as any);
    const res = await fetch(`${BASE}/voice/transcribe?language=${language}`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status}: ${text || res.statusText}`);
    }
    return res.json();
  },
  voiceSpeak: async (text: string, language: string): Promise<ArrayBuffer> => {
    const res = await fetch(`${BASE}/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`${res.status}: ${errText || res.statusText}`);
    }
    return res.arrayBuffer();
  },

  listLocations: (user_id = "demo-user") =>
    req(`/locations?user_id=${user_id}`),
  saveLocation: (body: {
    name: string;
    lat: number;
    lon: number;
    user_id?: string;
    is_vessel?: boolean;
  }) => req("/locations", { method: "POST", body: JSON.stringify(body) }),
  deleteLocation: (id: string) =>
    req(`/locations/${id}`, { method: "DELETE" }),

  geofenceCheck: (body: {
    name: string;
    lat: number;
    lon: number;
    user_id?: string;
  }) => req("/geofence/check", { method: "POST", body: JSON.stringify(body) }),

  getBoundaries: (region_id?: string) =>
    req(`/data/boundaries${region_id ? `?region_id=${region_id}` : ""}`),
  getRegion: (region_id?: string) =>
    req(`/region${region_id ? `?region_id=${region_id}` : ""}`),

  // India-wide region registry
  listRegions: (): Promise<{ regions: Region[]; default_region_id: string }> =>
    req("/regions"),
  detectRegion: (
    lat: number,
    lon: number,
  ): Promise<{ region: Region; distance_km: number }> =>
    req(`/regions/detect?lat=${lat}&lon=${lon}`),

  // Free-text location search (any Indian coastal place)
  geocode: (
    q: string,
  ): Promise<{ query: string; results: GeoResult[]; attribution: string }> =>
    req(`/geocode?q=${encodeURIComponent(q)}`),
};

export { BASE };
