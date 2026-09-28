import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/custody")({
  head: () => ({ meta: [
    { title: "Custody | Aperture Fund Services" },
    { name: "description", content: "Manage custody positions and actions." },
    { property: "og:title", content: "Custody | Aperture Fund Services" },
    { property: "og:description", content: "Manage custody positions and actions." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="custody" />,
});
