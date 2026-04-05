export type ChatMode = "voice_fast" | "chat_balanced" | "agent_strong";

export interface WeatherToolPayload {
  location_query: string;
  location_label: string;
  target_label: string;
  date_label: string;
  summary: string;
  icon_name: string;
  temperature: string;
  feels_like: string;
  temperature_value?: number | null;
  feels_like_value?: number | null;
  high_value?: number | null;
  low_value?: number | null;
  precipitation_probability?: number | null;
  wind: string;
  daily_outlook: string;
  is_current_day: boolean;
  source: string;
}

export interface UserProfilePayload {
  name: string;
  goal: string;
  mood: string;
  communication_style: string;
  response_length: string;
}

export interface ConversationSummary {
  id: number;
  title: string;
  created_at: string | null;
  messages: number;
  is_active: boolean;
}

export interface ConversationTurn {
  role: "user" | "assistant" | string;
  message: string;
  tool_kind?: string | null;
  tool_payload?: WeatherToolPayload | Record<string, unknown> | null;
}

export interface WorkspaceBootstrapResponse {
  profile: UserProfilePayload;
  conversations: ConversationSummary[];
  active_conversation_id: number | null;
  history: ConversationTurn[];
}

export interface ConversationWorkspaceResponse {
  conversations: ConversationSummary[];
  active_conversation_id: number | null;
  history: ConversationTurn[];
}

export interface ChatResponse {
  reply: string;
  mode_used: ChatMode | string;
  conversation_id: number | null;
  tts_url?: string | null;
  tool_kind?: string | null;
  tool_payload?: WeatherToolPayload | Record<string, unknown> | null;
}

export interface TranscribeResponse {
  transcribed_text: string;
}

export interface HealthResponse {
  status: string;
  listening: boolean;
}

export interface StatusResponse {
  listening: boolean;
  error?: string;
}

export interface LiveSnapshot {
  seq: number | null;
  transcript: string | null;
  reply: string | null;
  recording: boolean;
  processing: boolean;
  utter_ms: number | null;
  cycle_ms: number | null;
  utter_ts?: string | null;
  reply_ts?: string | null;
  tts_url?: string | null;
}

export interface Choice {
  label: string;
  value: string;
}

export interface LLMOptionsResponse {
  backend_choices: Choice[];
  current_backend: string;
  current_model: string;
  local_model_choices: Choice[];
  ollama_model_choices: Choice[];
  ollama_available: boolean;
  ollama_error?: string | null;
  message?: string | null;
}

export interface AudioDevice {
  index: number;
  name: string;
}

export interface AudioDevicesResponse {
  devices: AudioDevice[];
  selected_index: number | null;
  selected_name: string | null;
}

export interface AudioSelectResponse {
  ok: boolean;
  selected_index: number | null;
  selected_name: string | null;
  message?: string | null;
}
