import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import LoadingState from "./components/ui/LoadingState";
import StartupLoadingScreen from "./components/ui/StartupLoadingScreen";

const Home = lazy(() => import("./pages/Home"));
const Videos = lazy(() => import("./pages/Videos"));
const VideoDetail = lazy(() => import("./pages/VideoDetail"));
const Pigeons = lazy(() => import("./pages/Pigeons"));
const PigeonProfile = lazy(() => import("./pages/PigeonProfile"));
const Insights = lazy(() => import("./pages/Insights"));
const Review = lazy(() => import("./pages/Review"));
const Training = lazy(() => import("./pages/Training"));
const LabSetup = lazy(() => import("./pages/LabSetup"));
const NotFound = lazy(() => import("./pages/NotFound"));

export default function App() {
  return (
    <ErrorBoundary>
      <StartupLoadingScreen />
      <Suspense fallback={<LoadingState />}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/videos" element={<Videos />} />
            <Route path="/videos/:id" element={<VideoDetail />} />
            <Route path="/pigeons" element={<Pigeons />} />
            <Route path="/pigeons/:id" element={<PigeonProfile />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/review" element={<Review />} />
            <Route path="/training" element={<Training />} />
            <Route path="/settings" element={<LabSetup />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
