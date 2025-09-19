import Link from "next/link";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <div className="mx-auto max-w-7xl p-6">
          <header className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-semibold">🎯 Nehoris — GEO Audit</h1>
                <p className="text-sm text-gray-500">GPT-5 + Brand detection + Web search</p>
              </div>
              <nav className="flex gap-4">
                <Link href="/" className="px-4 py-2 bg-blue-600 text-white rounded-lg shadow hover:shadow-md">
                  Audit GEO
                </Link>
                <Link href="/analytics" className="px-4 py-2 bg-purple-600 text-white rounded-lg shadow hover:shadow-md">
                  📊 Analytics
                </Link>
                <Link href="/history" className="px-4 py-2 bg-green-600 text-white rounded-lg shadow hover:shadow-md">
                  📈 Historique
                </Link>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
