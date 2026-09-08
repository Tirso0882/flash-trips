import Link from "next/link";

interface PlannerPageProperties {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function PlannerPage({
  searchParams,
}: PlannerPageProperties) {
  const signInFailed = (await searchParams).sign_in === "failed";

  return (
    <main>
      <p className="eyebrow">Planner</p>
      <h1>Planner workspace</h1>
      <p>Sign in to continue to your private trip planning workspace.</p>
      {signInFailed ? (
        <p role="alert">Sign-in could not be completed. Please try again.</p>
      ) : null}
      <Link href="/api/auth/sign-in">Continue with Google</Link>
    </main>
  );
}
