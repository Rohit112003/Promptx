import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/nav")({
  head: () => ({ meta: [
    { title: "NAV Management | Aperture Fund Services" },
    { name: "description", content: "Review and publish fund net asset valuations." },
    { property: "og:title", content: "NAV Management | Aperture Fund Services" },
    { property: "og:description", content: "Review and publish fund net asset valuations." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="nav" />,
});
