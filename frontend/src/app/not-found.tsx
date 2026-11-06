import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 rounded-2xl bg-panel border border-border flex items-center justify-center text-2xl font-semibold text-accent mb-4 shadow-sm">
        404
      </div>
      <h1 className="text-2xl font-bold tracking-tight text-foreground">
        Page not found
      </h1>
      <p className="mt-2 text-sm text-muted max-w-md leading-relaxed">
        The review, repository, or page you requested does not exist or may belong to a different authorized workspace.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Link href="/">
          <Button variant="primary">Return to Overview</Button>
        </Link>
        <Link href="/reviews">
          <Button variant="secondary">Browse Reviews</Button>
        </Link>
      </div>
    </div>
  );
}
