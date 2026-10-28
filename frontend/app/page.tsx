"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

const TILES = [
  { href: "/rights", key: "home.understand", desc: "Plain-language guides to your rights across 20 areas of Indian law." },
  { href: "/ask", key: "home.ask", desc: "Get a source-grounded explanation with links to the official text." },
  { href: "/cases", key: "home.prepare", desc: "Organise facts, dates and documents in a private case workspace." },
  { href: "/documents", key: "home.review", desc: "Understand notices, agreements and contracts in simple language." },
  { href: "/judge", key: "home.analyse", desc: "See how both sides' arguments may be weighed — as an educational simulation." },
  { href: "/find-lawyer", key: "home.find", desc: "Search for qualified advocates by location, practice area and language." },
  { href: "/legal-aid", key: "home.aid", desc: "Free legal services you may be eligible for, and urgent help contacts." },
] as const;

export default function Home() {
  const { t } = useI18n();
  return (
    <>
      <section className="hero">
        <div className="rule" />
        <h1>{t("home.title")}</h1>
        <p>{t("home.lead")}</p>
      </section>
      <div className="grid">
        {TILES.map((tile) => (
          <Link key={tile.href} href={tile.href} className="tile">
            <h2>{t(tile.key)}</h2>
            <p>{tile.desc}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
