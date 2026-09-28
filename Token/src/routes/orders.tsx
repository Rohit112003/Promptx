import { createFileRoute } from "@tanstack/react-router";
import { FundConsole } from "@/components/fund/console";
export const Route = createFileRoute("/orders")({
  head: () => ({ meta: [
    { title: "Orders | Aperture Fund Services" },
    { name: "description", content: "Track fund subscriptions and redemptions." },
    { property: "og:title", content: "Orders | Aperture Fund Services" },
    { property: "og:description", content: "Track fund subscriptions and redemptions." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <FundConsole page="orders" />,
});
