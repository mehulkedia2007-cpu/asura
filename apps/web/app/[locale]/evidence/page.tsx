import { getTranslations } from "next-intl/server";
import { EvidenceBoard } from "@/components/EvidenceBoard";
import { HowTo } from "@/components/HowTo";
import { PageIntro } from "@/components/PageIntro";

export default async function EvidencePage() {
  const t = await getTranslations("p6");
  const workspace = await getTranslations("workspace");
  return (
    <main className="product-page">
      <PageIntro
        eyebrow={workspace("support")}
        title={t("title")}
        description={t("intro")}
        icon="evidence"
      />
      <HowTo section="evidence" />
      <div>
        <EvidenceBoard />
      </div>
    </main>
  );
}
