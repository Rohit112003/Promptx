import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/audit")({
  head: () => ({ meta: [
    { title: "Audit Trail | Aperture Fund Services" },
    { name: "description", content: "Verify fund operations against on-chain records." },
    { property: "og:title", content: "Audit Trail | Aperture Fund Services" },
    { property: "og:description", content: "Verify fund operations against on-chain records." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="audit" />,
});
