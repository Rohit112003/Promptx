import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/investors")({
  head: () => ({ meta: [
    { title: "Investors | Aperture Fund Services" },
    { name: "description", content: "Manage investor registration and compliance status." },
    { property: "og:title", content: "Investors | Aperture Fund Services" },
    { property: "og:description", content: "Manage investor registration and compliance status." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="investors" />,
});
