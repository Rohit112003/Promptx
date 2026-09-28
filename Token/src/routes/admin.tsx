import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/admin")({
  head: () => ({ meta: [
    { title: "Administration | Aperture Fund Services" },
    { name: "description", content: "Review fund controls and role assignments." },
    { property: "og:title", content: "Administration | Aperture Fund Services" },
    { property: "og:description", content: "Review fund controls and role assignments." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="admin" />,
});
