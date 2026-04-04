interface Props {
  open: boolean;
  projectName?: string | null;
  fileCount?: number;
}

export default function StringPatternBusyModal({
  open,
  projectName,
  fileCount,
}: Props) {
  if (!open) return null;

  const title = projectName
    ? `Detecting string pattern for ${projectName}...`
    : 'Detecting string pattern...';
  const details = fileCount && fileCount > 0
    ? `Analyzing ${fileCount} design file${fileCount === 1 ? '' : 's'}. Please wait.`
    : 'Please wait while Solarica analyzes the design file.';

  return (
    <div className="fixed inset-0 z-[70] flex cursor-wait items-center justify-center bg-black/35 backdrop-blur-sm">
      <div className="flex min-w-[280px] cursor-wait items-center gap-3 rounded-2xl bg-white px-5 py-4 shadow-2xl">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
        <div>
          <div className="text-sm font-semibold text-gray-900">{title}</div>
          <div className="text-xs text-gray-500">{details}</div>
        </div>
      </div>
    </div>
  );
}
