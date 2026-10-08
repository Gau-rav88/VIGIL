export default function CasesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Forensic Case Workbench</h1>
      </div>
      <div className="rounded-lg bg-slate-900 border border-slate-800 p-6">
        <div className="text-slate-500 text-center py-12">
          No cases currently open or under review.
        </div>
      </div>
    </div>
  );
}
