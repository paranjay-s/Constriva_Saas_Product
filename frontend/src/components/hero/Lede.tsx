import { siteContent } from "../../content/site";
import { LinkArrow } from "../ui/Icons";

export function Lede() {
  const { lede } = siteContent;

  return (
    <div className="lede" data-reveal>
      <p>{lede.text}</p>
      <a className="lede__link" href={lede.link.href}>
        {lede.link.label}
        <LinkArrow />
      </a>
    </div>
  );
}
