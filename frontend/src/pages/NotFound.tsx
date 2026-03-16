import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
      <span className="text-6xl mb-4">🐦</span>
      <h1 className="text-lg font-bold text-text-primary mb-2">
        Page not found
      </h1>
      <p className="text-sm text-text-secondary max-w-xs mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="px-5 py-2.5 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors"
      >
        Back to Home
      </Link>
    </div>
  );
}
