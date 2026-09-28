import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "Fund Overview | Aperture Fund Services" },
    { name: "description", content: "Monitor fund NAV, investor activity, orders and on-chain operations in Aperture's tokenised fund servicing console." },
    { property: "og:title", content: "Fund Overview | Aperture Fund Services" },
    { property: "og:description", content: "A secure workspace for tokenised fund operations, investors and on-chain reporting." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="dashboard" />,
});
