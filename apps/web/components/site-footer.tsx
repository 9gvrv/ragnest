import { site } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-6 py-6 text-[13px] text-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          © {site.year} {site.name}
        </p>
        <p className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span>Built by {site.author}</span>
          {site.social.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="transition-colors duration-150 hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </p>
      </div>
    </footer>
  );
}
