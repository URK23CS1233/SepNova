import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Paths accessible without authentication
const PUBLIC_PATHS = ["/", "/login", "/signup", "/api/health"];

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() { return request.cookies.getAll(); },
        setAll(cookiesToSet: { name: string; value: string; options?: any }[]) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const path = request.nextUrl.pathname;

  // Demo mode — cookie set by the landing-page demo button grants instant access
  if (request.cookies.get("sepnova_demo")?.value === "1") {
    return supabaseResponse;
  }

  // Allow public paths without auth
  const isPublic = PUBLIC_PATHS.some((p) => path === p || (p !== "/" && path.startsWith(p)));
  if (isPublic) {
    // If user is already authenticated and hits the landing/login/signup → redirect to dashboard
    if (path === "/" || path === "/login" || path === "/signup") {
      const { data: { user } } = await supabase.auth.getUser();
      if (user && path !== "/") {
        return NextResponse.redirect(new URL("/dashboard", request.url));
      }
    }
    return supabaseResponse;
  }

  // Protected routes — require auth
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("redirect", path);
    return NextResponse.redirect(loginUrl);
  }

  // Fetch role for route-based access control
  const { data: profile } = await supabase
    .from("user_profiles")
    .select("role, is_active")
    .eq("id", user.id)
    .single();

  if (!profile || !profile.is_active) {
    return NextResponse.redirect(new URL("/login?error=deactivated", request.url));
  }

  const role = profile.role;

  // Admin panel — admin only
  if (path.startsWith("/admin") && role !== "admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Model results — intensivist only
  if (path.startsWith("/results") && role !== "intensivist") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Insights — all clinical roles except lab_technician
  if (path.startsWith("/insights") && role === "lab_technician") {
    return NextResponse.redirect(new URL("/labs", request.url));
  }

  // Lab technicians — only /labs route
  if (role === "lab_technician" && !path.startsWith("/labs") && !path.startsWith("/api")) {
    return NextResponse.redirect(new URL("/labs", request.url));
  }

  return supabaseResponse;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico|webp)$).*)"],
};
