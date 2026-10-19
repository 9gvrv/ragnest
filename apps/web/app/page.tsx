import { AuthShell } from "@/components/auth-shell";

export default function Page() {
  return (
    <AuthShell
      title="Ask your documents."
      intro="Answers drawn only from what you have uploaded, with the page each one came from."
    >
      <p className="text-[15px] text-muted">Shell preview.</p>
    </AuthShell>
  );
}
