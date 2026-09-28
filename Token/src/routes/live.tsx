import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/live")({
  head: () => ({ meta: [
    { title: "Live Feed | Aperture Fund Services" },
    { name: "description", content: "Follow real-time tokenised fund events." },
    { property: "og:title", content: "Live Feed | Aperture Fund Services" },
    { property: "og:description", content: "Follow real-time tokenised fund events." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="live" />,
});
