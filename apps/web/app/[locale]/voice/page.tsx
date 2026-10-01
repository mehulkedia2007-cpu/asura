import { VoicePanel } from "@/components/VoicePanel";

export default function VoicePage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-8 px-6 py-12">
      <VoicePanel large />
    </main>
  );
}
