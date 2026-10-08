export default function VerifyPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Cryptographic Evidence Bundle Verifier</h1>
      <p className="text-sm text-slate-400">
        Upload a signed forensic evidence bundle (ZIP) to independently verify the cryptographic hash chain, Merkle root, and Ed25519 signature offline.
      </p>
      <div className="border-2 border-dashed border-slate-700 hover:border-emerald-500 rounded-xl p-12 text-center transition cursor-pointer bg-slate-900/50">
        <div className="text-slate-400">Drag and drop <code className="text-emerald-400">bundle.zip</code> here, or click to browse</div>
      </div>
    </div>
  );
}
