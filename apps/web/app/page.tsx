import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <p className="eyebrow">Flash Trips</p>
      <h1>Private trip planning</h1>
      <p>The product journeys are not implemented yet.</p>
      <nav aria-label="Application surfaces">
        <ul>
          <li>
            <Link href="/planner">Planner surface</Link>
          </li>
          <li>
            <Link href="/operator">Operator surface</Link>
          </li>
        </ul>
      </nav>
    </main>
  );
}
