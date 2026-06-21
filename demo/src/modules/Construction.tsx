import { Box } from "@mui/material";
import { PageHeader } from "../components/ui";
import { SimpleTable, pill, type Col } from "../components/Table";
import { TabPage } from "../components/Table";
import { ASSETS, type Asset } from "../data/catalog";
import { useDrawer } from "../components/AssetDrawer";
import DCLayer from "./DCLayer";

function AssetTable({ layer }: { layer: Asset["layer"] }) {
  const { open } = useDrawer();
  const rows = ASSETS.filter((a) => a.layer === layer);
  const cols: Col<Asset>[] = [
    { key: "id", label: "Asset", render: (a) => <b>{a.id}</b> },
    { key: "kind", label: "Type" },
    { key: "vendor", label: "Vendor" },
    { key: "model", label: "Model" },
    { key: "criticality", label: "Criticality" },
    { key: "status", label: "State", render: (a) => pill(a.status, a.status === "online" ? "#16a34a" : a.status === "warning" ? "#f59e0b" : a.status === "fault" ? "#dc2626" : "#94a3b8") },
    { key: "mw", label: "Rating", num: true, render: (a) => (a.mw != null ? `${a.mw} MW` : "—") },
  ];
  return <SimpleTable cols={cols} rows={rows} onRow={(a) => open({ type: "asset", data: a })} />;
}

export default function Construction() {
  return (
    <Box>
      <PageHeader title="Construction" subtitle="Execution Twin layers — DC strings, AC plant, BESS, Security" />
      <TabPage tabs={[
        { label: "DC Layer", node: <DCLayer embedded /> },
        { label: "AC Layer", node: <AssetTable layer="AC" /> },
        { label: "BESS Layer", node: <AssetTable layer="BESS" /> },
        { label: "Security Layer", node: <AssetTable layer="SECURITY" /> },
      ]} />
    </Box>
  );
}
