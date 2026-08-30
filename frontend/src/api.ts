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

export const api = {
  chat: (body: {
    message: string;
    session_id: string;
    language?: string | null;
    location?: { name?: string; lat: number; lon: number } | null;
    user_id?: string;
  }) => req("/chat", { method: "POST", body: JSON.stringify(body) }),

  getConversation: (session_id: string) =>
    req(`/conversations/${session_id}`),

  getAlerts: () => req("/alerts"),
  getNotifications: (user_id = "demo-user") =>
    req(`/notifications?user_id=${user_id}`),

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

  getBoundaries: () => req("/data/boundaries"),
  getRegion: () => req("/region"),
};

export { BASE };
