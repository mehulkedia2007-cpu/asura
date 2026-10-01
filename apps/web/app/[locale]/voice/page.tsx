import { getTranslations } from "next-intl/server";
import { PageIntro } from "@/components/PageIntro";
import { VoicePanel } from "@/components/VoicePanel";

export default async function VoicePage() {
  const t = await getTranslations("voice");
  const workspace = await getTranslations("workspace");
  return (
    <main className="product-page voice-page">
      <PageIntro
        eyebrow={workspace("support")}
        title={t("title")}
        description={t("intro")}
        icon="voice"
      />
      <VoicePanel large />
    </main>
  );
}
