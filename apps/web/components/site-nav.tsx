import Link from "next/link";
import { Container } from "@/components/container";
import { LogoMark } from "@/components/logo";
import { site } from "@/lib/site";

export function SiteNav() {
  return (
    <header className="border-b border-border">
      <nav aria-label="Main">
        <Container className="flex h-14 items-center justify-between gap-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-foreground"
          >
            <LogoMark />
            {site.name}
          </Link>

          <div className="flex items-center gap-1">
            <Link
              href="/login"
              className="rounded-full px-3 py-1.5 text-[13px] font-medium text-muted transition-colors duration-150 hover:text-foreground"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="rounded-full bg-foreground px-3.5 py-1.5 text-[13px] font-medium text-background transition-colors duration-150 hover:bg-foreground/90"
            >
              Sign up
            </Link>
          </div>
        </Container>
      </nav>
    </header>
  );
}
