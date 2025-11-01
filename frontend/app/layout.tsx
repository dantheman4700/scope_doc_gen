import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

import { getSessionUser } from "@/lib/auth";
import LogoutButton from "@/components/LogoutButton";

export const metadata: Metadata = {
  title: "Scope Doc Dashboard",
  description: "Internal scope document management portal"
};

export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  return (
    <html lang="en">
      <body>
        <nav>
          <div>
            <Link href="/projects">Scope Doc</Link>
          </div>
          <div className="nav-links">
            <Link href="/projects">Projects</Link>
            {user ? (
              <>
                <span>{user.email}</span>
                <LogoutButton />
              </>
            ) : (
              <Link href="/login">Sign in</Link>
            )}
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}

