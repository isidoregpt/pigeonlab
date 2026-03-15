import { Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout";
import Home from "./pages/Home";
import Videos from "./pages/Videos";
import Pigeons from "./pages/Pigeons";
import PigeonProfile from "./pages/PigeonProfile";
import Insights from "./pages/Insights";
import Review from "./pages/Review";
import Training from "./pages/Training";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/videos" element={<Videos />} />
        <Route path="/videos/:id" element={<Videos />} />
        <Route path="/pigeons" element={<Pigeons />} />
        <Route path="/pigeons/:id" element={<PigeonProfile />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/review" element={<Review />} />
        <Route path="/training" element={<Training />} />
      </Route>
    </Routes>
  );
}
