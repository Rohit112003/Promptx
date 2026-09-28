import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/transfers")({
  head: () => ({ meta: [
    { title: "Transfers | Aperture Fund Services" },
    { name: "description", content: "Transfer fund units between approved investors." },
    { property: "og:title", content: "Transfers | Aperture Fund Services" },
    { property: "og:description", content: "Transfer fund units between approved investors." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="transfers" />,
});
