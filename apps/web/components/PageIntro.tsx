import { Icon, type IconName } from "@/components/Icon";

export function PageIntro({
  eyebrow,
  title,
  description,
  icon,
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: IconName;
}) {
  return (
    <header className="page-intro">
      <div className="page-eyebrow">
        <Icon name={icon} />
        <span>{eyebrow}</span>
      </div>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
