import { Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import Home from "./pages/Home";
import Videos from "./pages/Videos";
import VideoDetail from "./pages/VideoDetail";
import Pigeons from "./pages/Pigeons";
import PigeonProfile from "./pages/PigeonProfile";
import Insights from "./pages/Insights";
import Review from "./pages/Review";
import Training from "./pages/Training";
import NotFound from "./pages/NotFound";
import LabSetup from "./pages/LabSetup";

export default function App() {
  return (
    <ErrorBoundary>
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
    </ErrorBoundary>
  );
}
