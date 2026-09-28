import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/reports")({
  head: () => ({ meta: [
    { title: "Reports | Aperture Fund Services" },
    { name: "description", content: "Generate investor statements and transaction reports." },
    { property: "og:title", content: "Reports | Aperture Fund Services" },
    { property: "og:description", content: "Generate investor statements and transaction reports." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="reports" />,
});
