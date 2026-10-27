import { Navigate, Route, Routes } from "react-router";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { TaskActionsProvider } from "./features/taskActions";
import { CalendarPage } from "./pages/CalendarPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlantDiaryTab } from "./pages/PlantDiaryTab";
import { PlantEditTab } from "./pages/PlantEditTab";
import { PlantPage } from "./pages/PlantPage";
import { PlantsPage } from "./pages/PlantsPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  const { username, checking } = useAuth();

  if (checking) return <Loading label="Avvio…" />;
  if (!username) return <LoginPage />;

  return (
    <TaskActionsProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="calendario" element={<CalendarPage />} />
          <Route path="piante" element={<PlantsPage />} />
          <Route path="piante/:plantId" element={<PlantPage />}>
            <Route index element={<PlantDiaryTab />} />
            <Route path="modifica" element={<PlantEditTab />} />
          </Route>
          <Route path="impostazioni" element={<SettingsPage />} />
          <Route path="login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </TaskActionsProvider>
  );
}
