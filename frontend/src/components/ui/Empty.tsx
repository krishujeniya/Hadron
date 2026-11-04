export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="border border-dashed border-border rounded-lg p-6 sm:p-8 text-center text-muted text-sm break-words min-w-0 max-w-full">
      {children}
    </div>
  );
}
