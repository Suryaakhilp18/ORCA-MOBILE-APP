import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Linking } from "react-native";
import {
  AudioPlayer,
  RecordingPresets,
  createAudioPlayer,
  getRecordingPermissionsAsync,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import { File, Paths } from "expo-file-system";

import { api } from "@/src/api";
import { Lang } from "@/src/context/AppContext";

export type VoiceState = "idle" | "recording" | "transcribing" | "speaking" | "error";

const MAX_RECORDING_MS = 30000;

// Voice Agent "Marine Copilot" — mic recording (expo-audio) -> ElevenLabs
// STT -> caller sends text to the existing /api/chat orchestrator exactly
// like typed input -> ElevenLabs TTS speaks the reply back.
// Follows the mandatory permission contract: check -> contextual ask ->
// respect canAskAgain -> "Open Settings" on hard denial, never a dead end.
export function useVoiceAgent(lang: Lang) {
  const [state, setState] = useState<VoiceState>("idle");
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);

  useEffect(() => {
    setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false }).catch(() => {});
    return () => {
      if (autoStopRef.current) clearTimeout(autoStopRef.current);
      playerRef.current?.remove?.();
    };
  }, []);

  const showSettingsPrompt = useCallback(() => {
    Alert.alert(
      "Microphone access needed",
      "Enable microphone access in Settings to ask ORCA questions by voice.",
      [
        { text: "Not now", style: "cancel" },
        { text: "Open Settings", onPress: () => Linking.openSettings() },
      ],
    );
  }, []);

  const ensurePermission = useCallback(async (): Promise<boolean> => {
    let status = await getRecordingPermissionsAsync();
    if (status.granted) return true;
    if (!status.canAskAgain) {
      showSettingsPrompt();
      return false;
    }
    status = await requestRecordingPermissionsAsync();
    if (status.granted) return true;
    if (!status.canAskAgain) showSettingsPrompt();
    return false;
  }, [showSettingsPrompt]);

  // Returns the transcribed text, or null if cancelled/failed.
  const startRecording = useCallback(async () => {
    const ok = await ensurePermission();
    if (!ok) return;
    try {
      // Only enable the record-capable audio session while actually
      // recording — leaving allowsRecording:true permanently routes later
      // playback to the iOS earpiece (quiet/inaudible) instead of the
      // speaker, making TTS look "broken" when it's actually just muted.
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setState("recording");
      autoStopRef.current = setTimeout(() => {
        stopRecording();
      }, MAX_RECORDING_MS);
    } catch {
      setState("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ensurePermission, recorder]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current);
      autoStopRef.current = null;
    }
    if (!recorder.isRecording) return null;
    try {
      await recorder.stop();
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      const uri = recorder.uri;
      if (!uri) {
        setState("idle");
        return null;
      }
      setState("transcribing");
      const { text } = await api.voiceTranscribe(uri, lang);
      setState("idle");
      return text?.trim() || null;
    } catch {
      setState("error");
      setTimeout(() => setState("idle"), 1500);
      return null;
    }
  }, [recorder, lang]);

  const speak = useCallback(async (text: string, language: Lang) => {
    try {
      const buf = await api.voiceSpeak(text, language);
      // Make sure we're OUT of record mode before playback, otherwise iOS
      // keeps routing audio to the earpiece instead of the main speaker.
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      const file = new File(Paths.cache, `orca-speak-${Date.now()}.mp3`);
      file.write(new Uint8Array(buf));
      const player = createAudioPlayer(file.uri);
      playerRef.current = player;
      const sub = player.addListener("playbackStatusUpdate", (status) => {
        if (status.didJustFinish) {
          sub.remove();
          player.remove();
          if (playerRef.current === player) playerRef.current = null;
          setState((s) => (s === "speaking" ? "idle" : s));
        }
      });
      player.play();
      // Only flip to "speaking" once playback has actually been kicked off,
      // not while still fetching/decoding the audio.
      setState("speaking");
    } catch {
      setState("idle");
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    playerRef.current?.pause?.();
    setState((s) => (s === "speaking" ? "idle" : s));
  }, []);

  return { state, startRecording, stopRecording, speak, stopSpeaking };
}
